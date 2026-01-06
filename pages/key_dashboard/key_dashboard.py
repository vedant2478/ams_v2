from datetime import datetime
from time import sleep
import subprocess
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
        self._door_timer_event = None
        self._can_poll_event = None
        self._mqtt_client = None

    # -----------------------------------------------------
    # SCREEN ENTER
    # -----------------------------------------------------
    def on_enter(self, *args):
        print("\n[DASHBOARD] Enter KeyDashboardScreen")

        # ✅ USE EXISTING CAN (DO NOT CREATE)
        ams_can = getattr(self.manager, "ams_can", None)
        if not ams_can:
            print("[ERROR] AMS_CAN not initialized in main")
            return

        print("[DASHBOARD] AMS_CAN id:", id(ams_can))
        print("[DASHBOARD] Keylists:", ams_can.key_lists)

        if not ams_can.key_lists:
            print("[ERROR] No keylists available")
            return

        session = self.manager.db_session

        # ---------------- ACCESS LOG ----------------
        ams_access_log = getattr(self.manager, "ams_access_log", None)
        if ams_access_log is None:
            ams_access_log = AMS_Access_Log(
                signInTime=datetime.now(TZ_INDIA),
                signInMode=self.manager.auth_mode,
                signInFailed=0,
                signInSucceed=1,
                signInUserId=self.manager.card_info["id"],
                doorOpenTime=datetime.now(TZ_INDIA),
                event_type_id=EVENT_DOOR_OPEN,
                is_posted=0,
            )
            session.add(ams_access_log)
            session.commit()
            self.manager.ams_access_log = ams_access_log

        # ---------------- ACTIVITY INFO ----------------
        self.activity_info = self.manager.activity_info
        self.activity_code = self.activity_info["code"]
        self.activity_name = self.activity_info["name"]

        # ---------------- UI ----------------
        self.reload_keys_from_db()
        self.populate_keys()
        self.unlock_activity_keys()

        # ---------------- EVENT LOG ----------------
        session.add(
            AMS_Event_Log(
                userId=self.manager.card_info["id"],
                keyId=None,
                activityId=self.activity_info["id"],
                eventId=EVENT_DOOR_OPEN,
                loginType=self.manager.final_auth_mode,
                access_log_id=ams_access_log.id,
                timeStamp=datetime.now(TZ_INDIA),
                event_type=EVENT_TYPE_EVENT,
                eventDesc=get_event_description(session, EVENT_DOOR_OPEN),
                is_posted=0,
            )
        )
        session.commit()

        # ---------------- UNLOCK DOOR ----------------
        subprocess.Popen(
            ["sudo", "python3", "solenoid.py", "1"],
            cwd="/home/rock/Desktop/ams_v2",
        )

        self.start_gpio_subscriber()

        self._can_poll_event = Clock.schedule_interval(
            self.poll_can_events, 0.2
        )

    # -----------------------------------------------------
    # MQTT GPIO
    # -----------------------------------------------------
    def start_gpio_subscriber(self):
        self._mqtt_client = mqtt.Client("kivy-door-subscriber")
        self._mqtt_client.on_connect = lambda c, u, f, r: c.subscribe("gpio/pin32")
        self._mqtt_client.on_message = self.on_mqtt_message
        self._mqtt_client.connect("localhost", 1883, 60)
        self._mqtt_client.loop_start()

    def on_mqtt_message(self, client, userdata, msg):
        value = int(msg.payload.decode())
        if value == 1 and not self._door_open:
            self._door_open = True
            self.start_door_timer()
        elif value == 0 and self._door_open:
            self._door_open = False
            self.stop_door_timer()

    # -----------------------------------------------------
    # DOOR TIMER
    # -----------------------------------------------------
    def start_door_timer(self):
        self.time_remaining = str(self.MAX_DOOR_TIME)
        self.progress_value = 0.0
        self._door_timer_event = Clock.schedule_interval(
            self.door_timer_tick, 1
        )

    def stop_door_timer(self):
        if self._door_timer_event:
            self._door_timer_event.cancel()
            self._door_timer_event = None

    def door_timer_tick(self, dt):
        remaining = int(self.time_remaining) - 1
        self.time_remaining = str(max(0, remaining))
        self.progress_value += 1 / float(self.MAX_DOOR_TIME)

        if remaining <= 0:
            self.go_back()

    # -----------------------------------------------------
    # CAN POLLING
    # -----------------------------------------------------
    def poll_can_events(self, dt):
        ams_can = self.manager.ams_can

        if ams_can.key_taken_event:
            self.handle_key_taken_commit(ams_can.key_taken_id)
            set_key_status_by_peg_id(
                self.manager.db_session,
                ams_can.key_taken_id,
                1,
            )
            ams_can.key_taken_event = False
            self.reload_keys_from_db()
            self.update_key_widgets()

    # -----------------------------------------------------
    # DB COMMIT
    # -----------------------------------------------------
    def handle_key_taken_commit(self, peg_id):
        session = self.manager.db_session
        user = self.manager.card_info

        key = session.query(AMS_Keys).filter(
            AMS_Keys.peg_id == peg_id
        ).first()

        if not key:
            return

        key.keyTakenBy = user["id"]
        key.keyTakenByUser = user["name"]
        key.keyTakenAtTime = datetime.now(TZ_INDIA)
        key.keyStatus = SLOT_STATUS_KEY_NOT_PRESENT

        session.add(
            AMS_Event_Log(
                userId=user["id"],
                keyId=key.id,
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

    # -----------------------------------------------------
    # UI HELPERS
    # -----------------------------------------------------
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
            )
            self.key_widgets[str(key["id"])] = widget
            grid.add_widget(widget)

        self.update_key_widgets()

    def update_key_widgets(self):
        for key in self.keys_data:
            widget = self.key_widgets.get(str(key["id"]))
            if widget:
                widget.set_status("IN" if key["status"] == 0 else "OUT")

    def unlock_activity_keys(self):
        ams_can = self.manager.ams_can
        for key in self.keys_data:
            ams_can.unlock_single_key(
                int(key["strip"]),
                int(key["position"]),
            )

    # -----------------------------------------------------
    # EXIT
    # -----------------------------------------------------
    def go_back(self):
        subprocess.Popen(
            ["sudo", "python3", "solenoid.py", "0"],
            cwd="/home/rock/Desktop/ams_v2",
        )

        if self._door_timer_event:
            self._door_timer_event.cancel()

        if self._can_poll_event:
            self._can_poll_event.cancel()

        if self._mqtt_client:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()

        self.manager.current = "activity"
