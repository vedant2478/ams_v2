from datetime import datetime
import subprocess
import paho.mqtt.client as mqtt
import mraa

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

    MAX_DOOR_TIME = 30

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.key_widgets = {}

        self._door_open = False
        self.door_open_seconds = 0

        self._door_timer_event = None
        self._can_poll_event = None
        self._mqtt_client = None

        # 🔴 LOCAL CAN OBJECT (ONLY HERE)
        self.ams_can = None

    # -----------------------------------------------------
    # SCREEN ENTER
    # -----------------------------------------------------
    def on_enter(self, *args):
        print("[KEY_DASHBOARD] Enter")

        session = self.manager.db_session

        # ---------------- ACCESS LOG ----------------
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

        # ---------------- ACTIVITY ----------------
        self.activity_info = self.manager.activity_info
        self.activity_code = self.activity_info["code"]
        self.activity_name = self.activity_info["name"]

        # ---------------- LOAD UI ----------------
        self.reload_keys_from_db()
        self.populate_keys()

        # ---------------- CREATE LOCAL CAN ----------------
        print("[KEY_DASHBOARD] Initializing local AMS_CAN")
        self.ams_can = AMS_CAN()

        # Allow discovery
        self.ams_can.get_version_number(1)
        self.ams_can.get_version_number(2)

        for strip in self.ams_can.key_lists:
            self.ams_can.lock_all_positions(strip)
            self.ams_can.set_all_LED_OFF(strip)


        # Unlock activity keys
        self.unlock_activity_keys()

        # ---------------- EVENT LOG ----------------
        session.add(
            AMS_Event_Log(
                userId=self.manager.card_info["id"],
                keyId=None,
                activityId=self.activity_info["id"],
                eventId=EVENT_DOOR_OPEN,
                loginType=self.manager.final_auth_mode,
                access_log_id=access_log.id,
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

        # ---------------- MQTT ----------------
        self.start_gpio_subscriber()

        # ---------------- CAN POLLING ----------------
        self._can_poll_event = Clock.schedule_interval(
            self.poll_can_events, 0.2
        )

    # -----------------------------------------------------
    # MQTT GPIO
    # -----------------------------------------------------
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

    # -----------------------------------------------------
    # DOOR EVENTS
    # -----------------------------------------------------
    def on_door_opened(self):
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
        self.progress_value = self.door_open_seconds / float(self.MAX_DOOR_TIME)

        if self.door_open_seconds >= self.MAX_DOOR_TIME:
            self.go_back()

    def on_door_closed(self):
        self._door_open = False
        if self._door_timer_event:
            self._door_timer_event.cancel()
            self._door_timer_event = None

    # -----------------------------------------------------
    # CAN POLLING (LOCAL ONLY)
    # -----------------------------------------------------
    def poll_can_events(self, dt):
        if not self.ams_can:
            return

        if self.ams_can.key_taken_event:
            self.handle_key_taken_commit(self.ams_can.key_taken_id)
            set_key_status_by_peg_id(
                session=self.manager.db_session,
                peg_id=self.ams_can.key_taken_id,
                status=1,
            )
            self.ams_can.key_taken_event = False
            self.reload_keys_from_db()
            self.update_key_widgets()

        if self.ams_can.key_inserted_event:
            set_key_status_by_peg_id(
                session=self.manager.db_session,
                peg_id=self.ams_can.key_inserted_id,
                status=0,
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

    # -----------------------------------------------------
    # UI HELPERS
    # -----------------------------------------------------
    def reload_keys_from_db(self):
        self.keys_data = get_keys_for_activity(
            session=self.manager.db_session,
            activity_id=self.activity_info["id"],
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

    def unlock_activity_keys(self):
        for key in self.keys_data:
            self.ams_can.unlock_single_key(
                int(key["strip"]),
                int(key["position"]),
            )
            self.ams_can.set_single_LED_state(int(key["strip"]), int(key["position"]) , CAN_LED_STATE_ON)
    # -----------------------------------------------------
    # EXIT CLEANUP (CRITICAL)
    # -----------------------------------------------------
    def go_back(self):
        print("[KEY_DASHBOARD] Exit → unlock keys, LEDs off, cleanup")

        # ---------------- STOP CAN POLLING ----------------
        if self._can_poll_event:
            self._can_poll_event.cancel()
            self._can_poll_event = None

        # ---------------- UNLOCK ALL KEYS + LED OFF ----------------
        if self.ams_can and self.ams_can.key_lists:
            for strip in self.ams_can.key_lists:
                print(f"[KEY_DASHBOARD] Unlocking strip {strip} & turning LEDs OFF")
                self.ams_can.unlock_all_positions(strip)
                self.ams_can.set_all_LED_OFF(strip)

        # ---------------- CLEAN CAN ----------------
        if self.ams_can:
            print("[KEY_DASHBOARD] Cleaning CAN")
            self.ams_can.cleanup()
            self.ams_can = None

        # ---------------- STOP MQTT ----------------
        if self._mqtt_client:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()
            self._mqtt_client = None

        # ---------------- STOP TIMER ----------------
        if self._door_timer_event:
            self._door_timer_event.cancel()
            self._door_timer_event = None

        # ---------------- LOCK DOOR ----------------
        subprocess.Popen(
            ["sudo", "python3", "solenoid.py", "0"],
            cwd="/home/rock/Desktop/ams_v2",
        )

        self.manager.current = "activity"
