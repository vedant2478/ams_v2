from datetime import datetime
import subprocess
import logging
import paho.mqtt.client as mqtt

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
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
from test2 import sync_hardware_to_db  # Import the sync function

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
# KEY ITEM
# =========================================================
class KeyItem(ButtonBehavior, BoxLayout):
    key_id = StringProperty("")
    key_name = StringProperty("")
    status_text = StringProperty("IN")
    status_color = ListProperty([0, 1, 0, 1])
    dashboard = ObjectProperty(None)

    def set_status(self, status):
        self.status_text = status
        self.status_color = [0, 1, 0, 1] if status == "IN" else [1, 0, 0, 1]
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
    time_remaining = StringProperty("30")
    progress_value = NumericProperty(0.0)
    keys_data = ListProperty([])
    key_interactions = ListProperty([])

    MAX_DOOR_TIME = 60

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.key_widgets = {}
        self._door_open = False
        self.door_open_seconds = 0

        self._door_timer_event = None
        self._can_poll_event = None
        self._mqtt_client = None

        self.ams_can = None

    # =====================================================
    # SCREEN ENTER
    # =====================================================
    def on_enter(self, *args):
        log.info("[ENTER] KeyDashboard entered")

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

        # -------- ACTIVITY --------
        self.activity_info = self.manager.activity_info
        self.activity_code = self.activity_info["code"]
        self.activity_name = self.activity_info["name"]

        # -------- HARDWARE SYNC --------
        log.info("[SYNC] Starting hardware sync to database...")
        
        # Sync hardware state to DB using the standalone function
        sync_success = sync_hardware_to_db(session)
        
        if sync_success:
            log.info("[SYNC] Hardware sync completed successfully")
        else:
            log.warning("[SYNC] Hardware sync failed or no strips detected")

        # Reload keys from DB (now reflects hardware state)
        self.reload_keys_from_db()
        self.populate_keys()

        # -------- CAN INIT (already done in sync_hardware_to_db) --------
        # Get reference to CAN (sync function already initialized it)
        log.info("[CAN] Getting AMS_CAN instance")
        self.ams_can = AMS_CAN()
        # No need to call get_version_number again, sync already did it

        # Start deterministic CAN sequence for activity keys
        Clock.schedule_once(self._can_step_led_on_all, 1.5)

        # door state
        self._door_open = False
        self.door_open_seconds = 0
        self.time_remaining = str(self.MAX_DOOR_TIME)
        self.progress_value = 0.0

        # -------- MQTT --------
        self.start_gpio_subscriber()

        # -------- CAN POLLING --------
        self._can_poll_event = Clock.schedule_interval(
            self.poll_can_events, 0.2
        )

    # =====================================================
    # CAN SEQUENCE
    # =====================================================
    def _can_step_led_on_all(self, dt):
        log.info("[CAN-1] LED ON (ALL)")
        for strip in self.ams_can.key_lists:
            self.ams_can.set_all_LED_ON(strip, False)
        Clock.schedule_once(self._can_step_lock_all, 1.0)

    def _can_step_lock_all(self, dt):
        log.info("[CAN-2] LOCK ALL KEYS")
        for strip in self.ams_can.key_lists:
            self.ams_can.lock_all_positions(strip)
        Clock.schedule_once(self._can_step_led_off_all, 1.0)

    def _can_step_led_off_all(self, dt):
        log.info("[CAN-3] LED OFF (ALL)")
        for strip in self.ams_can.key_lists:
            self.ams_can.set_all_LED_OFF(strip)
        Clock.schedule_once(self._can_step_unlock_activity, 1.0)

    def _can_step_unlock_activity(self, dt):
        log.info("[CAN-4] UNLOCK ACTIVITY KEYS")
        for key in self.keys_data:
            strip = int(key["strip"])
            pos = int(key["position"])
            self.ams_can.unlock_single_key(strip, pos)
            self.ams_can.set_single_LED_state(strip, pos, CAN_LED_STATE_ON)
        subprocess.Popen(
            ["sudo", "python3", "solenoid.py", "1"],
            cwd="/home/rock/Desktop/ams_v2",
        )

    # =====================================================
    # MQTT GPIO
    # =====================================================
    def start_gpio_subscriber(self):
        self._mqtt_client = mqtt.Client("kivy-door-subscriber")
        self._mqtt_client.on_connect = self.on_mqtt_connect
        self._mqtt_client.on_message = self.on_mqtt_message
        self._mqtt_client.connect("localhost", 1883, 60)
        self._mqtt_client.loop_start()

    def on_mqtt_connect(self, client, userdata, flags, rc):
        client.subscribe("gpio/pin32")

    def on_mqtt_message(self, client, userdata, msg):
        value = int(msg.payload.decode())
        if value == 1 and not self._door_open:
            Clock.schedule_once(lambda dt: self.on_door_opened())
        elif value == 0 and self._door_open:
            Clock.schedule_once(lambda dt: self.on_door_closed())

    # =====================================================
    # DOOR EVENTS
    # =====================================================
    def on_door_opened(self):
        log.info("[DOOR] Opened")

        subprocess.Popen(
            ["sudo", "python3", "solenoid.py", "0"],
            cwd="/home/rock/Desktop/ams_v2",
        )

        self._door_open = True
        self.door_open_seconds = 0
        self.time_remaining = str(self.MAX_DOOR_TIME)
        self.progress_value = 0.0

        self._door_timer_event = Clock.schedule_interval(
            self.door_timer_tick, 1
        )

    def door_timer_tick(self, dt):
        self.door_open_seconds += 1
        remaining = max(0, self.MAX_DOOR_TIME - self.door_open_seconds)

        self.time_remaining = str(remaining)
        self.progress_value = (
            self.door_open_seconds / float(self.MAX_DOOR_TIME)
        )

        if self.door_open_seconds >= self.MAX_DOOR_TIME:
            print("[DOOR] Max time exceeded, auto-closing door")

    def on_door_closed(self):
        log.info("[DOOR] Closed")
        self._door_open = False

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

        self._shutdown_can_and_mqtt()
        self.key_interactions = []
        self.manager.current = "activity_done"

    # =====================================================
    # SHUTDOWN HELPER
    # =====================================================
    def _shutdown_can_and_mqtt(self):
        if self._can_poll_event:
            self._can_poll_event.cancel()
            self._can_poll_event = None

        if self.ams_can:
            for strip in self.ams_can.key_lists:
                self.ams_can.unlock_all_positions(strip)
                self.ams_can.set_all_LED_OFF(strip)
            self.ams_can.cleanup()
            self.ams_can = None

        if self._mqtt_client:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()
            self._mqtt_client = None

        if self._door_timer_event:
            self._door_timer_event.cancel()
            self._door_timer_event = None

    # =====================================================
    # NAME LOOKUP
    # =====================================================
    def _get_key_name_by_peg(self, peg_id):
        log.debug(f"keys_data for lookup: {self.keys_data}")
        for k in self.keys_data:
            if str(k.get("peg_id")) == str(peg_id):
                desc = k.get("description") or k.get("name")
                if desc:
                    return desc
                break
        return f"Key {peg_id}"

    # =====================================================
    # CAN POLLING
    # =====================================================
    def poll_can_events(self, dt):
        if not self.ams_can:
            return

        # KEY TAKEN (removed)
        if self.ams_can.key_taken_event:
            peg_id = self.ams_can.key_taken_id
            self.handle_key_taken_commit(peg_id)

            key_name = self._get_key_name_by_peg(peg_id)
            taken_time = datetime.now(TZ_INDIA)

            self.key_interactions.append({
                "key_name": key_name,
                "peg_id": peg_id,
                "taken_timestamp": taken_time,
                "returned_timestamp": None,
            })

            set_key_status_by_peg_id(self.manager.db_session, peg_id, 1)
            self.ams_can.key_taken_event = False
            self.reload_keys_from_db()
            self.update_key_widgets()

        # KEY RETURNED (inserted)
        if self.ams_can.key_inserted_event:
            peg_id = self.ams_can.key_inserted_id
            key_name = self._get_key_name_by_peg(peg_id)
            returned_time = datetime.now(TZ_INDIA)

            updated = False
            for ev in reversed(self.key_interactions):
                if ev["key_name"] == key_name and ev["returned_timestamp"] is None:
                    ev["returned_timestamp"] = returned_time
                    updated = True
                    break

            if not updated:
                self.key_interactions.append({
                    "key_name": key_name,
                    "peg_id": peg_id,
                    "taken_timestamp": None,
                    "returned_timestamp": returned_time,
                })

            set_key_status_by_peg_id(self.manager.db_session, peg_id, 0)
            self.ams_can.key_inserted_event = False
            self.reload_keys_from_db()
            self.update_key_widgets()

    # =====================================================
    # DB COMMIT
    # =====================================================
    def handle_key_taken_commit(self, peg_id):
        session = self.manager.db_session
        user = self.manager.card_info

        key_record = session.query(AMS_Keys).filter(
            AMS_Keys.peg_id == peg_id
        ).first()
        if not key_record:
            return

        session.query(AMS_Keys).filter(
            AMS_Keys.peg_id == peg_id
        ).update(
            {
                "keyTakenBy": user["id"],
                "keyTakenByUser": user["name"],
                "current_pos_strip_id": None,
                "current_pos_slot_no": None,
                "keyTakenAtTime": datetime.now(TZ_INDIA),
                "keyStatus": SLOT_STATUS_KEY_NOT_PRESENT,
            }
        )

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
                eventDesc=get_event_description(
                    session, EVENT_KEY_TAKEN_CORRECT
                ),
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
                widget.set_status(
                    "IN" if key["status"] == 0 else "OUT"
                )

    def open_done_page(self, key_name: str, status: str, key_id: str):
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

        self._shutdown_can_and_mqtt()
        self.key_interactions = []
        self.manager.current = "activity_done"

    # =====================================================
    # EXIT CLEANUP
    # =====================================================
    def go_back(self):
        self._shutdown_can_and_mqtt()

        subprocess.Popen(
            ["sudo", "python3", "solenoid.py", "0"],
            cwd="/home/rock/Desktop/ams_v2",
        )

        self.key_interactions = []
        self.manager.current = "activity"
