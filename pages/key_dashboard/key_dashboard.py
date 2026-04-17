from datetime import datetime
import subprocess
import logging
import time
import threading

import paho.mqtt.client as mqtt

from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.graphics import Color, RoundedRectangle
from kivy.properties import (
    StringProperty,
    ListProperty,
    ObjectProperty,
    NumericProperty,
)
from kivy.clock import Clock

from components.base_screen import BaseScreen
from db import get_keys_for_activity, set_key_status_by_peg_id
from amscan import AMS_CAN, CAN_LED_STATE_ON
from hardware_sync import sync_hardware_to_db

from csi_ams.model import (
    AMS_Keys,
    AMS_Access_Log,
    AMS_Event_Log,
    EVENT_DOOR_OPEN,
    EVENT_KEY_TAKEN_CORRECT,
    EVENT_TYPE_EVENT,
)
from csi_ams.utils.commons import (
    SLOT_STATUS_KEY_NOT_PRESENT,
    TZ_INDIA,
    get_event_description,
)

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("KEY_DASHBOARD")


# =========================================================
# LOADING POPUP — NO WHITE BORDER
# =========================================================
class SolenoidLoadingPopup(ModalView):
    """Beautiful loading popup shown while door is opening."""

    def __init__(self, **kwargs):
        super().__init__(
            size_hint=(0.65, 0.55),
            auto_dismiss=False,
            background='',
            background_color=[0, 0, 0, 0.75],
            **kwargs
        )

        container = BoxLayout(orientation='vertical', padding=0, spacing=0)
        content = BoxLayout(orientation='vertical', padding=40, spacing=20)

        with content.canvas.before:
            Color(0.06, 0.12, 0.20, 0.98)
            self.rect = RoundedRectangle(
                pos=content.pos,
                size=content.size,
                radius=[24, 24, 24, 24]
            )

        content.bind(pos=self._update_rect, size=self._update_rect)

        title_label = Label(
            text="[b]OPENING DOOR[/b]",
            markup=True,
            font_size='30sp',
            size_hint_y=0.28,
            color=(0.20, 0.85, 0.45, 1)
        )
        content.add_widget(title_label)

        self.progress = ProgressBar(max=100, size_hint_y=0.12)
        self.progress.value = 0
        content.add_widget(self.progress)

        Clock.schedule_interval(self._animate_progress, 0.04)

        message = Label(
            text="Please wait while the system\nprepares access to your keys...",
            font_size='17sp',
            color=(0.65, 0.75, 0.85, 1),
            halign='center',
            size_hint_y=0.30
        )
        content.add_widget(message)

        self.status_label = Label(
            text="Initializing...",
            font_size='13sp',
            color=(0.45, 0.55, 0.65, 1),
            italic=True,
            size_hint_y=0.30
        )
        content.add_widget(self.status_label)

        container.add_widget(content)
        self.add_widget(container)

    def _animate_progress(self, dt):
        self.progress.value = (self.progress.value + 2) % 100

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

    def update_status(self, status_text):
        self.status_label.text = status_text


# =========================================================
# KEY ITEM (one row in the list)
# =========================================================
class KeyItem(ButtonBehavior, BoxLayout):
    key_id = StringProperty("")
    key_name = StringProperty("")
    status_text = StringProperty("IN")
    status_color = ListProperty([0, 1, 0, 1])
    dashboard = ObjectProperty(None)

    def set_status(self, status):
        self.status_text = status
        self.status_color = [0.15, 0.85, 0.35, 1] if status == "IN" else [1, 0.25, 0.25, 1]
        log.debug(f"[UI] Key {self.key_name} status → {status}")

    def on_release(self):
        if self.dashboard:
            self.dashboard.open_done_page(
                self.key_name,
                self.status_text,
                self.key_id,
            )


# =========================================================
# DASHBOARD SCREEN
# =========================================================
class KeyDashboardScreen(BaseScreen):

    activity_code = StringProperty("")
    activity_name = StringProperty("")
    user_name = StringProperty("")
    time_remaining = StringProperty("60")
    progress_value = NumericProperty(0.0)
    keys_data = ListProperty([])
    key_interactions = ListProperty([])

    MAX_DOOR_TIME = 60
    MIN_DOOR_OPEN_TIME = 3

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.key_widgets = {}
        self._door_open = False
        self.door_open_seconds = 0
        self._door_opened_timestamp = None

        self._door_timer_event = None
        self._mqtt_client = None

        self.ams_can = None
        self._screen_active = False
        self._loading_popup = None

        # Misplaced key blinking
        self._blink_event = None
        self._blink_state = False
        self._misplaced_slots = set()

        # Background CAN poll thread
        self._can_poll_thread_running = False
        self._can_poll_thread = None

    # =====================================================
    # SCREEN LIFECYCLE
    # =====================================================
    def on_enter(self, *args):
        log.info("[ENTER] KeyDashboard entered")
        self._screen_active = True
        self._show_loading_popup()
        threading.Thread(target=self._initialize_hardware_thread, daemon=True).start()

    def _initialize_hardware_thread(self):
        """Heavy initialization runs in background thread."""
        try:
            Clock.schedule_once(lambda dt: self._update_popup_status("Connecting to hardware..."), 0)

            session = self.manager.db_session

            # -------- ACCESS LOG --------
            access_log = AMS_Access_Log(
                signInTime=datetime.now(TZ_INDIA),
                signInMode=self.manager.auth_mode,
                signInFailed=0,
                signInSucceed=1,
                signInUserId=self.manager.card_info["id"],
                doorOpenTime=datetime.now(TZ_INDIA),
                event_type_id=EVENT_DOOR_OPEN,
                is_posted=0,
            )
            session.add(access_log)
            session.commit()
            self.manager.ams_access_log = access_log

            # -------- ACTIVITY + USER --------
            self.activity_info = self.manager.activity_info
            Clock.schedule_once(lambda dt: self._update_activity_ui(), 0)

            # -------- CAN INIT --------
            Clock.schedule_once(lambda dt: self._update_popup_status("Connecting to CAN bus..."), 0)
            log.info("[CAN] Using Global AMS_CAN")
            self.ams_can = self.manager.ams_can

            if self.ams_can:
                log.info(f"[CAN] Connected. Detected {len(self.ams_can.key_lists)} strip(s)")
            else:
                log.warning("[CAN] Global AMS_CAN instance is not available")

            # -------- HARDWARE SYNC --------
            Clock.schedule_once(lambda dt: self._update_popup_status("Syncing hardware state..."), 0)
            log.info("[SYNC] Starting hardware sync...")
            sync_success = sync_hardware_to_db(session, self.ams_can)

            if sync_success:
                log.info("[SYNC] Sync completed successfully")
            else:
                log.warning("[SYNC] Hardware sync failed")

            session.flush()
            session.commit()
            time.sleep(0.3)
            session.expire_all()

            Clock.schedule_once(lambda dt: self._update_popup_status("Loading keys..."), 0)
            self.reload_keys_from_db()
            log.info(f"[SYNC] Loaded {len(self.keys_data)} keys from DB")

            for k in self.keys_data:
                log.debug(
                    f"[  Key ] id={k.get('id')} name={k.get('name')} "
                    f"status={k.get('status')} peg={k.get('peg_id')}"
                )

            Clock.schedule_once(lambda dt: self._update_popup_status("Preparing access..."), 0)
            Clock.schedule_once(lambda dt: self._finalize_initialization(), 0)

        except Exception as e:
            log.error(f"[INIT] Hardware initialization failed: {e}")
            import traceback
            traceback.print_exc()
            Clock.schedule_once(lambda dt: self._dismiss_loading_popup(), 0)

    def _update_popup_status(self, status_text):
        if self._loading_popup:
            self._loading_popup.update_status(status_text)

    def _update_activity_ui(self):
        """Update activity + user info on main thread."""
        self.activity_code = self.activity_info.get("code", "")
        self.activity_name = self.activity_info.get("name", "")
        card_info = self.manager.card_info
        self.user_name = card_info.get("name", "") if card_info else ""

    def _finalize_initialization(self):
        """Called on main thread after background init is done."""
        self.populate_keys()

        self._door_open = False
        self.door_open_seconds = 0
        self._door_opened_timestamp = None
        self.time_remaining = str(self.MAX_DOOR_TIME)
        self.progress_value = 0.0

        # MQTT subscriber for door sensor
        self.start_gpio_subscriber()

        # CAN sequence runs in its own thread (avoids blocking main thread)
        threading.Thread(target=self._run_can_sequence, daemon=True).start()

        # CAN event poll loop runs in its own thread
        self._start_can_poll_thread()

    def on_leave(self, *args):
        """Called when leaving the screen."""
        log.info("[LEAVE] KeyDashboard leaving")
        self._screen_active = False
        self._dismiss_loading_popup()
        self._stop_misplaced_blink()
        self._misplaced_slots.clear()
        self._shutdown_can_and_mqtt()

    # =====================================================
    # LOADING POPUP HELPERS
    # =====================================================
    def _show_loading_popup(self):
        if self._loading_popup:
            return
        log.info("[POPUP] Showing loading popup")
        self._loading_popup = SolenoidLoadingPopup()
        self._loading_popup.open()

    def _dismiss_loading_popup(self):
        if self._loading_popup:
            log.info("[POPUP] Dismissing loading popup")
            self._loading_popup.dismiss()
            self._loading_popup = None

    # =====================================================
    # CAN INITIALIZATION SEQUENCE (background thread)
    # =====================================================
    def _run_can_sequence(self):
        """
        Run the full LED/lock CAN init sequence off the main thread.
        All sleep() calls stay here, not on the UI thread.
        """
        try:
            if not self._screen_active or not self.ams_can:
                Clock.schedule_once(lambda dt: self._dismiss_loading_popup(), 0)
                return

            # Guard: need at least one strip
            if not self.ams_can.key_lists:
                log.warning("[CAN SEQ] No strips — skipping sequence")
                Clock.schedule_once(lambda dt: self._activate_solenoid_and_finish(), 0)
                return

            # Step 1 — LED ON (all)
            Clock.schedule_once(lambda dt: self._update_popup_status("Activating LEDs..."), 0)
            log.info("[CAN-1] LED ON (ALL)")
            for strip in list(self.ams_can.key_lists):
                self.ams_can.set_all_LED_ON(strip, False)

            if not self._screen_active:
                return
            time.sleep(0.8)

            # Step 2 — LOCK ALL
            Clock.schedule_once(lambda dt: self._update_popup_status("Securing locks..."), 0)
            log.info("[CAN-2] LOCK ALL KEYS")
            for strip in list(self.ams_can.key_lists):
                self.ams_can.lock_all_positions(strip)

            if not self._screen_active:
                return
            time.sleep(0.8)

            # Step 3 — LED OFF (all)
            Clock.schedule_once(lambda dt: self._update_popup_status("Configuring access..."), 0)
            log.info("[CAN-3] LED OFF (ALL)")
            for strip in list(self.ams_can.key_lists):
                self.ams_can.set_all_LED_OFF(strip)

            if not self._screen_active:
                return
            time.sleep(0.8)

            # Step 4 — UNLOCK activity keys + LED ON
            Clock.schedule_once(lambda dt: self._update_popup_status("Unlocking authorized keys..."), 0)
            log.info("[CAN-4] UNLOCK ACTIVITY KEYS")
            for key in list(self.keys_data):
                if not self._screen_active:
                    return
                strip = int(key["strip"])
                pos = int(key["position"])
                self.ams_can.unlock_single_key(strip, pos)

            # Done — open solenoid on main thread
            Clock.schedule_once(lambda dt: self._activate_solenoid_and_finish(), 0)

        except Exception as e:
            log.error(f"[CAN SEQ] Error: {e}")
            import traceback
            traceback.print_exc()
            Clock.schedule_once(lambda dt: self._dismiss_loading_popup(), 0)

    def _activate_solenoid_and_finish(self):
        """Runs on main thread — open door solenoid and dismiss popup."""
        self._update_popup_status("Opening door lock...")
        subprocess.Popen(
            ["sudo", "python3", "pub.py"],
            cwd="/home/rock/Desktop/ams_v2",
        )
        subprocess.Popen(
            ["sudo", "python3", "solenoid.py", "1"],
            cwd="/home/rock/Desktop/ams_v2",
        )
        Clock.schedule_once(lambda dt: self._dismiss_loading_popup(), 1.0)

    # =====================================================
    # MISPLACED KEY BLINKING
    # =====================================================
    def _start_misplaced_blink(self):
        if self._blink_event:
            return
        self._blink_state = False
        self._blink_event = Clock.schedule_interval(self._blink_tick, 0.5)

    def _stop_misplaced_blink(self):
        if self._blink_event:
            self._blink_event.cancel()
            self._blink_event = None
        if not self.ams_can:
            return
        for strip, pos in list(self._misplaced_slots):
            try:
                self.ams_can.set_single_LED_state(strip, pos, CAN_LED_STATE_ON)
            except Exception:
                pass

    def _blink_tick(self, dt):
        if not self.ams_can:
            return
        self._blink_state = not self._blink_state
        for strip, pos in list(self._misplaced_slots):
            try:
                state = CAN_LED_STATE_ON if self._blink_state else 0
                self.ams_can.set_single_LED_state(strip, pos, state)
            except Exception:
                pass

    # =====================================================
    # CAN POLL — BACKGROUND THREAD
    # =====================================================
    def _start_can_poll_thread(self):
        self._can_poll_thread_running = True
        self._can_poll_thread = threading.Thread(
            target=self._can_poll_loop, daemon=True
        )
        self._can_poll_thread.start()

    def _stop_can_poll_thread(self):
        self._can_poll_thread_running = False
        # Thread is daemon so it will die with the process; no join needed.

    def _can_poll_loop(self):
        """
        Runs in a background thread.
        Reads CAN event flags and delegates handling to the main thread
        via Clock.schedule_once so Kivy/DB/UI are only touched from main.
        """
        while self._can_poll_thread_running:
            time.sleep(0.1)

            if not self.ams_can or not self._screen_active:
                continue

            # KEY TAKEN (removed from peg)
            if self.ams_can.key_taken_event:
                peg_id = self.ams_can.key_taken_id
                actual_pos = self.ams_can.key_taken_position_slot
                actual_strip = self.ams_can.key_taken_position_list
                self.ams_can.key_taken_event = False  # clear before scheduling
                Clock.schedule_once(
                    lambda dt, p=peg_id, s=actual_strip, o=actual_pos:
                    self._handle_key_taken(p, s, o)
                )

            # KEY INSERTED (returned to peg)
            if self.ams_can.key_inserted_event:
                peg_id = self.ams_can.key_inserted_id
                actual_pos = self.ams_can.key_inserted_position_slot
                actual_strip = self.ams_can.key_inserted_position_list
                self.ams_can.key_inserted_event = False
                Clock.schedule_once(
                    lambda dt, p=peg_id, s=actual_strip, o=actual_pos:
                    self._handle_key_inserted(p, s, o)
                )

    # =====================================================
    # KEY EVENT HANDLERS — run on main thread
    # =====================================================
    def _handle_key_taken(self, peg_id, actual_strip, actual_pos):
        """Handle a key-taken event (main thread)."""
        if not self._screen_active:
            return

        log.info(f"[KEY TAKEN] peg={peg_id} strip={actual_strip} pos={actual_pos}")
        self.handle_key_taken_commit(peg_id, actual_strip, actual_pos)

        key_name = self._get_key_name_by_peg(peg_id)
        taken_time = datetime.now(TZ_INDIA)

        self.key_interactions.append({
            "key_name": key_name,
            "peg_id": peg_id,
            "taken_timestamp": taken_time,
            "returned_timestamp": None,
        })

        set_key_status_by_peg_id(self.manager.db_session, peg_id, 1)
        self.reload_keys_from_db()
        self.update_key_widgets()

    def _handle_key_inserted(self, peg_id, actual_strip, actual_pos):
        """Handle a key-inserted event (main thread)."""
        if not self._screen_active:
            return

        log.info(f"[KEY INSERTED] peg={peg_id} strip={actual_strip} pos={actual_pos}")
        key_name = self._get_key_name_by_peg(peg_id)
        returned_time = datetime.now(TZ_INDIA)

        # -------- MISPLACED CHECK --------
        expected_pos = None
        expected_strip = None
        for k in self.keys_data:
            if str(k.get("peg_id")) == str(peg_id):
                expected_pos = int(k.get("position"))
                expected_strip = int(k.get("strip"))
                break

        if expected_pos is not None and (
            expected_pos != actual_pos or expected_strip != actual_strip
        ):
            log.warning(
                f"[MISPLACED] Key {key_name} peg_id={peg_id} expected "
                f"strip={expected_strip},pos={expected_pos} but inserted at "
                f"strip={actual_strip},pos={actual_pos}"
            )
            self._misplaced_slots.add((actual_strip, actual_pos))
            self._start_misplaced_blink()
        else:
            if (actual_strip, actual_pos) in self._misplaced_slots:
                self._misplaced_slots.discard((actual_strip, actual_pos))
                if not self._misplaced_slots:
                    self._stop_misplaced_blink()

        # -------- DB + SELF-HEALING --------
        updated = False
        session = self.manager.db_session
        key_record = session.query(AMS_Keys).filter(
            AMS_Keys.peg_id == str(peg_id)
        ).first()

        if not key_record:
            log.warning(
                f"[DB] Inserted peg_id={peg_id} not found. "
                f"Fallback on Strip {actual_strip} Slot {actual_pos}"
            )
            key_record = session.query(AMS_Keys).filter(
                AMS_Keys.keyStrip == actual_strip,
                AMS_Keys.keyPosition == actual_pos,
                AMS_Keys.deletedAt == None
            ).first()

            if key_record:
                log.info(
                    f"[DB] Self-healing (INSERT): Updating "
                    f"{key_record.keyName} to peg_id {peg_id}"
                )
                key_record.peg_id = str(peg_id)
                session.commit()
                key_name = key_record.keyName

                for k in self.keys_data:
                    if k.get("id") == key_record.id:
                        k["peg_id"] = str(peg_id)
                        break

        for ev in reversed(self.key_interactions):
            if ev["key_name"] == key_name and ev["returned_timestamp"] is None:
                ev["returned_timestamp"] = returned_time
                updated = True
                break

        if not updated:
            log.info(
                f"[KEY INSERT] Key {key_name} returned but not in session history"
            )
            taken_timestamp = None
            if key_record and key_record.keyTakenAtTime:
                taken_timestamp = key_record.keyTakenAtTime

            self.key_interactions.append({
                "key_name": key_name,
                "peg_id": peg_id,
                "taken_timestamp": taken_timestamp,
                "returned_timestamp": returned_time,
            })

        set_key_status_by_peg_id(self.manager.db_session, peg_id, 0)
        self.reload_keys_from_db()
        self.update_key_widgets()

    # =====================================================
    # MQTT GPIO
    # =====================================================
    def start_gpio_subscriber(self):
        try:
            self._mqtt_client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION1, "kivy-door-subscriber"
            )
        except AttributeError:
            # Fallback for Paho MQTT < 2.0
            self._mqtt_client = mqtt.Client("kivy-door-subscriber")

        self._mqtt_client.on_connect = self.on_mqtt_connect
        self._mqtt_client.on_message = self.on_mqtt_message
        try:
            self._mqtt_client.connect("localhost", 1883, 60)
            self._mqtt_client.loop_start()
        except Exception as e:
            log.warning(f"[MQTT] Failed to connect: {e}")

    def on_mqtt_connect(self, client, userdata, flags, rc):
        client.subscribe("gpio/pin32")

    def on_mqtt_message(self, client, userdata, msg):
        if not self._screen_active:
            return

        try:
            value = int(msg.payload.decode())
        except ValueError:
            return

        if value == 1 and not self._door_open:
            Clock.schedule_once(lambda dt: self.on_door_opened())
        elif value == 0 and self._door_open:
            Clock.schedule_once(lambda dt: self.on_door_closed())

    # =====================================================
    # DOOR EVENTS
    # =====================================================
    def on_door_opened(self):
        if not self._screen_active:
            return

        log.info("[DOOR] Opened")
        subprocess.Popen(
            ["sudo", "python3", "solenoid.py", "0"],
            cwd="/home/rock/Desktop/ams_v2",
        )

        self._door_open = True
        self._door_opened_timestamp = datetime.now()
        self.door_open_seconds = 0
        self.time_remaining = str(self.MAX_DOOR_TIME)
        self.progress_value = 0.0

        self._door_timer_event = Clock.schedule_interval(self.door_timer_tick, 1)

    def door_timer_tick(self, dt):
        if not self._screen_active:
            return

        self.door_open_seconds += 1
        remaining = max(0, self.MAX_DOOR_TIME - self.door_open_seconds)
        self.time_remaining = str(remaining)
        self.progress_value = self.door_open_seconds / float(self.MAX_DOOR_TIME)

        if self.door_open_seconds >= self.MAX_DOOR_TIME:
            log.warning("[DOOR] Max time exceeded")

    def on_door_closed(self):
        if not self._screen_active:
            return

        if self._door_opened_timestamp:
            elapsed = (datetime.now() - self._door_opened_timestamp).total_seconds()
            if elapsed < self.MIN_DOOR_OPEN_TIME:
                log.info(
                    f"[DOOR] Close too soon ({elapsed:.1f}s < {self.MIN_DOOR_OPEN_TIME}s)"
                )
                return

        log.info("[DOOR] Closed")
        self._door_open = False

        subprocess.Popen(["sudo", "pkill", "-f", "pub.py"])

        if self._door_timer_event:
            self._door_timer_event.cancel()
            self._door_timer_event = None

        cards = []
        for inter in self.key_interactions:
            taken_ts = inter.get("taken_timestamp")
            returned_ts = inter.get("returned_timestamp")
            cards.append({
                "key_name": inter["key_name"],
                "taken_text": taken_ts.strftime("%Y-%m-%d %H:%M:%S") if taken_ts else "",
                "returned_text": returned_ts.strftime("%Y-%m-%d %H:%M:%S") if returned_ts else "",
            })

        self.manager.cards = cards
        self.manager.timestamp_text = datetime.now(TZ_INDIA).strftime(
            "%Y-%m-%d %H:%M:%S %Z"
        )

        self._screen_active = False
        self._dismiss_loading_popup()
        self._stop_misplaced_blink()
        self._misplaced_slots.clear()
        self._shutdown_can_and_mqtt()
        self.key_interactions = []
        self.manager.current = "activity_done"

    # =====================================================
    # SHUTDOWN HELPER
    # =====================================================
    def _shutdown_can_and_mqtt(self):
        log.info("[SHUTDOWN] Cleaning up resources...")

        # Stop poll thread first
        self._stop_can_poll_thread()

        # Stop door timer
        if self._door_timer_event:
            self._door_timer_event.cancel()
            self._door_timer_event = None

        # Stop misplaced blinking
        self._stop_misplaced_blink()
        self._misplaced_slots.clear()

        # Disconnect MQTT
        if self._mqtt_client:
            try:
                self._mqtt_client.loop_stop()
                self._mqtt_client.disconnect()
            except Exception:
                pass
            self._mqtt_client = None
            log.info("[SHUTDOWN] MQTT disconnected")

        subprocess.Popen(["sudo", "pkill", "-f", "pub.py"])

        # CAN cleanup
        if hasattr(self, 'ams_can') and self.ams_can:
            try:
                for strip in self.ams_can.key_lists:
                    self.ams_can.unlock_all_positions(strip)
                    self.ams_can.set_all_LED_OFF(strip)
            except Exception as e:
                log.error(f"[SHUTDOWN] CAN error: {e}")

            self.ams_can = None
            log.info("[SHUTDOWN] CAN activities stopped")

        log.info("[SHUTDOWN] Complete")

    # =====================================================
    # NAME LOOKUP
    # =====================================================
    def _get_key_name_by_peg(self, peg_id):
        for k in self.keys_data:
            if str(k.get("peg_id")) == str(peg_id):
                desc = k.get("description") or k.get("name")
                if desc:
                    return desc
                break
        return f"Key {peg_id}"

    # =====================================================
    # DB COMMIT — KEY TAKEN
    # =====================================================
    def handle_key_taken_commit(self, peg_id, strip, slot):
        session = self.manager.db_session
        user = self.manager.card_info

        key_record = session.query(AMS_Keys).filter(
            AMS_Keys.peg_id == peg_id
        ).first()

        if not key_record:
            log.warning(
                f"[DB] No key for peg_id={peg_id}. Slot lookup strip={strip} pos={slot}"
            )
            key_record = session.query(AMS_Keys).filter(
                AMS_Keys.keyStrip == strip,
                AMS_Keys.keyPosition == slot,
                AMS_Keys.deletedAt == None
            ).first()

            if key_record:
                log.info(
                    f"[DB] Self-healing: Updating {key_record.keyName} to peg_id {peg_id}"
                )
                key_record.peg_id = str(peg_id)
                session.commit()

                for k in self.keys_data:
                    if k.get("id") == key_record.id:
                        k["peg_id"] = str(peg_id)

        if not key_record:
            log.error(f"[DB] Failed to bind key taken: Strip {strip} Slot {slot} not in DB")
            return

        session.query(AMS_Keys).filter(
            AMS_Keys.id == key_record.id
        ).update({
            "keyTakenBy": user["id"],
            "keyTakenByUser": user["name"],
            "current_pos_strip_id": None,
            "current_pos_slot_no": None,
            "keyTakenAtTime": datetime.now(TZ_INDIA),
            "keyStatus": SLOT_STATUS_KEY_NOT_PRESENT,
        })

        session.add(
            AMS_Event_Log(
                userId=user["id"],
                keyId=key_record.id,
                activityId=self.activity_info["id"],
                eventId=EVENT_KEY_TAKEN_CORRECT,
                loginType=self.manager.final_auth_mode,
                access_log_id=self.manager.ams_access_log.id,
                timeStamp=datetime.now(TZ_INDIA),
                event_type=EVENT_TYPE_EVENT,
                eventDesc=get_event_description(session, EVENT_KEY_TAKEN_CORRECT),
                is_posted=0,
            )
        )
        session.commit()

    # =====================================================
    # UI HELPERS
    # =====================================================
    def reload_keys_from_db(self):
        self.keys_data = get_keys_for_activity(
            self.manager.db_session,
            self.activity_info["id"],
        )

    def populate_keys(self):
        grid = self.ids.key_grid
        grid.clear_widgets()
        self.key_widgets.clear()

        for key in self.keys_data:
            widget = KeyItem(
                key_id=str(key["id"]),
                key_name=key["name"],
                dashboard=self,
            )
            self.key_widgets[str(key["id"])] = widget
            grid.add_widget(widget)

        self.update_key_widgets()

    def update_key_widgets(self):
        for key in self.keys_data:
            widget = self.key_widgets.get(str(key["id"]))
            if widget:
                widget.set_status("IN" if key["status"] == 0 else "OUT")

    def open_done_page(self, key_name: str, status: str, key_id: str):
        """Navigate to activity_done (early exit or manual close)."""
        cards = []
        for inter in self.key_interactions:
            taken_ts = inter.get("taken_timestamp")
            returned_ts = inter.get("returned_timestamp")
            cards.append({
                "key_name": inter["key_name"],
                "taken_text": taken_ts.strftime("%Y-%m-%d %H:%M:%S") if taken_ts else "",
                "returned_text": returned_ts.strftime("%Y-%m-%d %H:%M:%S") if returned_ts else "",
            })

        self.manager.cards = cards
        self.manager.timestamp_text = datetime.now(TZ_INDIA).strftime(
            "%Y-%m-%d %H:%M:%S %Z"
        )

        self._screen_active = False
        self._dismiss_loading_popup()
        self._stop_misplaced_blink()
        self._misplaced_slots.clear()
        self._shutdown_can_and_mqtt()
        self.key_interactions = []
        self.manager.current = "activity_done"

    # =====================================================
    # GO BACK / EXIT
    # =====================================================
    def go_back(self):
        log.info("[GO_BACK] User cancelled")
        self._screen_active = False
        self._dismiss_loading_popup()
        self._stop_misplaced_blink()
        self._misplaced_slots.clear()
        self._shutdown_can_and_mqtt()

        subprocess.Popen(
            ["sudo", "python3", "solenoid.py", "0"],
            cwd="/home/rock/Desktop/ams_v2",
        )

        self.key_interactions = []
        self.manager.current = "activity"
