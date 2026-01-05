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
from amscan import AMS_CAN

from csi_ams.model import (
    EVENT_DOOR_OPEN,
    AMS_Keys,
    AMS_Event_Log,
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

    # -----------------------------------------------------
    # SCREEN ENTER
    # -----------------------------------------------------
    def on_enter(self, *args):
        print("[UI] Enter KeyDashboardScreen")

        session = self.manager.db_session
        ams_access_log = self.manager.ams_access_log

        self.activity_info = getattr(self.manager, "activity_info", None)
        if not self.activity_info:
            print("[ERROR] No activity info")
            return

        self.activity_code = self.activity_info["code"]
        self.activity_name = self.activity_info["name"]

        self.ensure_can_up()

        ams_access_log.doorOpenTime = datetime.now(TZ_INDIA)
        session.commit()

        eventDesc = get_event_description(session, EVENT_DOOR_OPEN)

        if not hasattr(self.manager, "ams_can"):
            self.manager.ams_can = AMS_CAN()
            self.lock_all_keys()

        self.reload_keys_from_db()
        self.populate_keys()
        self.unlock_activity_keys()

        ams_event_log = AMS_Event_Log(
            userId=self.manager.card_info["id"],
            keyId=None,
            activityId=self.activity_info["id"],
            eventId=EVENT_DOOR_OPEN,
            loginType=self.manager.final_auth_mode,
            access_log_id=ams_access_log.id,
            timeStamp=datetime.now(TZ_INDIA),
            event_type=EVENT_TYPE_EVENT,
            eventDesc=eventDesc,
            is_posted=0,
        )
        session.add(ams_event_log)
        session.commit()

        # 🔓 Unlock door
        subprocess.Popen(
            ["sudo", "python3", "solenoid.py", "1"],
            cwd="/home/rock/Desktop/ams_v2",
        )

        # 🚪 Start MQTT GPIO listener
        self.start_gpio_subscriber()

        # ✅ START CAN POLLING IMMEDIATELY (IMPORTANT)
        if not self._can_poll_event:
            self._can_poll_event = Clock.schedule_interval(
                self.poll_can_events, 0.2
            )

    # -----------------------------------------------------
    # CAN
    # -----------------------------------------------------
    def ensure_can_up(self):
        subprocess.run(["sudo", "ip", "link", "set", "can0", "down"])
        sleep(0.2)
        subprocess.run(
            ["sudo", "ip", "link", "set", "can0",
             "up", "type", "can", "bitrate", "125000"]
        )
        sleep(0.2)

    def lock_all_keys(self):
        ams_can = self.manager.ams_can
        for strip in ams_can.key_lists or [1, 2]:
            ams_can.lock_all_positions(strip)
            ams_can.set_all_LED_OFF(strip)

    # -----------------------------------------------------
    # MQTT GPIO (THREAD SAFE)
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
        print("[MQTT] Door GPIO:", value)

        if value == 1 and not self._door_open:
            Clock.schedule_once(lambda dt: self.on_door_opened())

        elif value == 0 and self._door_open:
            Clock.schedule_once(lambda dt: self.on_door_closed())

    # -----------------------------------------------------
    # DOOR EVENTS
    # -----------------------------------------------------
    def on_door_opened(self):
        if self._door_open:
            return

        print("[DOOR] OPEN")
        self._door_open = True
        self.door_open_seconds = 0
        self.time_remaining = str(self.MAX_DOOR_TIME)
        self.progress_value = 0.0

        if not self._door_timer_event:
            self._door_timer_event = Clock.schedule_interval(
                self.door_timer_tick, 1
            )

    def door_timer_tick(self, dt):
        if not self._door_open:
            return

        self.door_open_seconds += 1
        remaining = max(0, self.MAX_DOOR_TIME - self.door_open_seconds)

        self.time_remaining = str(remaining)
        self.progress_value = self.door_open_seconds / float(self.MAX_DOOR_TIME)

        if self.door_open_seconds >= self.MAX_DOOR_TIME:
            print("[TIMEOUT] Door open too long")
            self.go_back()

    def on_door_closed(self):
        if not self._door_open:
            return

        print("[DOOR] CLOSED")
        self._door_open = False

        if self._door_timer_event:
            self._door_timer_event.cancel()
            self._door_timer_event = None

        self.door_open_seconds = 0

    # -----------------------------------------------------
    # CAN POLLING (FIXED)
    # -----------------------------------------------------
    def poll_can_events(self, dt):
        print("[CAN] poll_can_events running")

        ams_can = self.manager.ams_can

        if ams_can.key_taken_event:
            print(f"[CAN] Key taken | PEG ID = {ams_can.key_taken_id}")

            self.handle_key_taken_commit(ams_can.key_taken_id)
            set_key_status_by_peg_id(ams_can.key_taken_id, 1)

            ams_can.key_taken_event = False
            self.reload_keys_from_db()
            self.update_key_widgets()

        if ams_can.key_inserted_event:
            print(f"[CAN] Key inserted | PEG ID = {ams_can.key_inserted_id}")

            set_key_status_by_peg_id(ams_can.key_inserted_id, 0)
            ams_can.key_inserted_event = False
            print(self.keys_data)
            self.reload_keys_from_db()
            self.update_key_widgets()

    # -----------------------------------------------------
    # DB COMMIT
    # -----------------------------------------------------
    def handle_key_taken_commit(self, peg_id):
        session = self.manager.db_session
        user = self.manager.card_info

        key_record = (
            session.query(AMS_Keys)
            .filter(AMS_Keys.peg_id == peg_id)
            .first()
        )
        if not key_record:
            print("[DB][WARN] Key record not found")
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
                "color": "White",
            }
        )

        eventDesc = get_event_description(
            session, EVENT_KEY_TAKEN_CORRECT
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
                eventDesc=eventDesc,
                is_posted=0,
            )
        )
        session.commit()

        print(f"[DB] Key taken committed → {key_record.keyName}")

    # -----------------------------------------------------
    # UI + DB
    # -----------------------------------------------------
    def reload_keys_from_db(self):
        self.keys_data = get_keys_for_activity(self.activity_info["id"])

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
        print("[UI] Cleanup & exit")

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
