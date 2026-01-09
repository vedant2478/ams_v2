from datetime import datetime
import subprocess
import paho.mqtt.client as mqtt
import mraa
import logging

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
from amscan import AMS_CAN, CAN_LED_STATE_ON, CAN_LED_STATE_OFF

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
# LOGGING SETUP
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
        log.debug(f"[UI] Key {self.key_name} status set to {status}")

    def on_release(self):
        if self.dashboard:
            log.info(f"[UI] Key pressed: {self.key_name}")
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

    MAX_DOOR_TIME = 30

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.key_widgets = {}
        self._door_open = False
        self.door_open_seconds = 0

        self._door_timer_event = None
        self._can_poll_event = None
        self._mqtt_client = None

        self.ams_can = None

    # -----------------------------------------------------
    # SCREEN ENTER
    # -----------------------------------------------------
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
        log.info("[DB] Access log created")

        # -------- ACTIVITY --------
        self.activity_info = self.manager.activity_info
        self.activity_code = self.activity_info["code"]
        self.activity_name = self.activity_info["name"]
        log.info(f"[ACTIVITY] {self.activity_name} ({self.activity_code})")

        # -------- LOAD UI --------
        self.reload_keys_from_db()
        self.populate_keys()

        # -------- INIT CAN --------
        log.info("[CAN] Initializing AMS_CAN")
        self.ams_can = AMS_CAN()

        log.debug("[CAN] Requesting version numbers")
        self.ams_can.get_version_number(1)
        self.ams_can.get_version_number(2)

        # IMPORTANT: Start controlled CAN sequence
        Clock.schedule_once(self._can_step_led_on_all, 1.5)

        # -------- UNLOCK DOOR --------
        subprocess.Popen(
            ["sudo", "python3", "solenoid.py", "1"],
            cwd="/home/rock/Desktop/ams_v2",
        )
        log.info("[DOOR] Door unlocked")

        # -------- MQTT --------
        self.start_gpio_subscriber()

        # -------- CAN POLLING --------
        self._can_poll_event = Clock.schedule_interval(
            self.poll_can_events, 0.2
        )

    # =====================================================
    # CAN INITIALIZATION SEQUENCE (STRICT ORDER)
    # =====================================================
    def _can_step_led_on_all(self, dt):
        log.info("[CAN-STEP-1] Turning ON all LEDs")
        for strip in self.ams_can.key_lists:
            log.debug(f"[CAN] LED ON strip {strip}")
            self.ams_can.set_all_LED_ON(strip)

        Clock.schedule_once(self._can_step_lock_all, 1.0)

    def _can_step_lock_all(self, dt):
        log.info("[CAN-STEP-2] Locking ALL keys")
        for strip in self.ams_can.key_lists:
            log.debug(f"[CAN] Lock strip {strip}")
            self.ams_can.lock_all_positions(strip)

        Clock.schedule_once(self._can_step_led_off_all, 1.0)

    def _can_step_led_off_all(self, dt):
        log.info("[CAN-STEP-3] Turning OFF all LEDs")
        for strip in self.ams_can.key_lists:
            log.debug(f"[CAN] LED OFF strip {strip}")
            self.ams_can.set_all_LED_OFF(strip)

        Clock.schedule_once(self._can_step_unlock_activity, 1.0)

    def _can_step_unlock_activity(self, dt):
        log.info("[CAN-STEP-4] Unlocking ACTIVITY keys")
        for key in self.keys_data:
            strip = int(key["strip"])
            pos = int(key["position"])

            log.debug(f"[CAN] Unlock key strip={strip} pos={pos}")
            self.ams_can.unlock_single_key(strip, pos)
            self.ams_can.set_single_LED_state(
                strip, pos, CAN_LED_STATE_ON
            )

    # -----------------------------------------------------
    # CAN POLLING
    # -----------------------------------------------------
    def poll_can_events(self, dt):
        if not self.ams_can:
            return

        if self.ams_can.key_taken_event:
            peg_id = self.ams_can.key_taken_id
            log.info(f"[CAN] Key taken event: peg_id={peg_id}")

            self.handle_key_taken_commit(peg_id)
            set_key_status_by_peg_id(
                self.manager.db_session, peg_id, 1
            )

            self.ams_can.key_taken_event = False
            self.reload_keys_from_db()
            self.update_key_widgets()

        if self.ams_can.key_inserted_event:
            peg_id = self.ams_can.key_inserted_id
            log.info(f"[CAN] Key inserted event: peg_id={peg_id}")

            set_key_status_by_peg_id(
                self.manager.db_session, peg_id, 0
            )

            self.ams_can.key_inserted_event = False
            self.reload_keys_from_db()
            self.update_key_widgets()

    # -----------------------------------------------------
    # DB COMMIT
    # -----------------------------------------------------
    def handle_key_taken_commit(self, peg_id):
        session = self.manager.db_session
        user = self.manager.card_info

        log.info(f"[DB] Committing key taken: peg_id={peg_id}")

        key_record = session.query(AMS_Keys).filter(
            AMS_Keys.peg_id == peg_id
        ).first()

        if not key_record:
            log.error("[DB] Key record not found")
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
        log.info("[DB] Key taken committed successfully")

    # -----------------------------------------------------
    # UI HELPERS
    # -----------------------------------------------------
    def reload_keys_from_db(self):
        log.debug("[DB] Reloading keys from DB")
        self.keys_data = get_keys_for_activity(
            self.manager.db_session,
            self.activity_info["id"],
        )

    def populate_keys(self):
        log.debug("[UI] Populating key widgets")
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
        log.debug("[UI] Updating key widgets")
        for key in self.keys_data:
            widget = self.key_widgets.get(str(key["id"]))
            if widget:
                widget.set_status("IN" if key["status"] == 0 else "OUT")

    # -----------------------------------------------------
    # EXIT CLEANUP
    # -----------------------------------------------------
    def go_back(self):
        log.warning("[EXIT] Cleaning up dashboard")

        if self._can_poll_event:
            self._can_poll_event.cancel()

        if self.ams_can:
            for strip in self.ams_can.key_lists:
                log.debug(f"[CAN] Unlock all + LED off strip {strip}")
                self.ams_can.unlock_all_positions(strip)
                self.ams_can.set_all_LED_OFF(strip)

            self.ams_can.cleanup()
            self.ams_can = None

        if self._mqtt_client:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()

        if self._door_timer_event:
            self._door_timer_event.cancel()

        subprocess.Popen(
            ["sudo", "python3", "solenoid.py", "0"],
            cwd="/home/rock/Desktop/ams_v2",
        )
        log.info("[DOOR] Door locked")

        self.manager.current = "activity"
