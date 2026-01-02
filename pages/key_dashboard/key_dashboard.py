from time import sleep
import subprocess

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import (
    StringProperty,
    ListProperty,
    ObjectProperty,
    NumericProperty
)
from kivy.clock import Clock

from components.base_screen import BaseScreen
from db import get_keys_for_activity, set_key_status_by_peg_id
from test import AMS_CAN


# =========================================================
# KEY ITEM (UI COMPONENT)
# =========================================================
class KeyItem(ButtonBehavior, BoxLayout):
    key_id = StringProperty("")
    key_name = StringProperty("")
    status_text = StringProperty("IN")
    status_color = ListProperty([0, 1, 0, 1])
    dashboard = ObjectProperty(None)

    def set_status(self, status: str):
        self.status_text = status
        self.status_color = [0, 1, 0, 1] if status == "IN" else [1, 0, 0, 1]

    def on_release(self):
        if self.dashboard:
            self.dashboard.open_done_page(
                self.key_name,
                self.status_text,
                self.key_id
            )


# =========================================================
# DASHBOARD SCREEN
# =========================================================
class KeyDashboardScreen(BaseScreen):

    activity_code = StringProperty("")
    activity_name = StringProperty("")
    time_remaining = StringProperty("30")

    # 🔑 TIMER + PROGRESS
    door_timer = NumericProperty(0)
    max_door_time = NumericProperty(30)
    progress_value = NumericProperty(0.0)

    keys_data = ListProperty([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.key_widgets = {}
        self._can_poll_event = None
        self._door_timer_event = None

        self._door_monitor_started = False
        self._last_door_state = 0   # 0 = closed, 1 = open

    # -----------------------------------------------------
    # SCREEN ENTER
    # -----------------------------------------------------
    def on_enter(self, *args):
        print("[UI] ▶ Entered KeyDashboardScreen")

        self.activity_info = getattr(self.manager, "activity_info", None)
        if not self.activity_info:
            print("[UI] ❌ No activity info")
            return

        self.activity_code = self.activity_info.get("code", "")
        self.activity_name = self.activity_info.get("name", "")
        self.time_remaining = str(self.max_door_time)

        self.ensure_can_up()

        if not hasattr(self.manager, "ams_can"):
            self.manager.ams_can = AMS_CAN()
            self._setup_can_and_lock_all()

        self.reload_keys_from_db()
        self.populate_keys()
        self.unlock_activity_keys()

        # 🔥 Open solenoid
        subprocess.Popen(["sudo", "python3", "solenoid.py", "1"])

        # 🚪 Start door monitoring
        self.start_door_monitor()

    # -----------------------------------------------------
    def ensure_can_up(self):
        subprocess.run(["sudo", "ip", "link", "set", "can0", "down"])
        sleep(0.5)
        subprocess.run([
            "sudo", "ip", "link", "set", "can0",
            "up", "type", "can", "bitrate", "125000"
        ])
        sleep(0.5)

    # -----------------------------------------------------
    def start_door_monitor(self):
        if not self._door_monitor_started:
            self._door_monitor_started = True
            Clock.schedule_interval(self.monitor_door_status, 0.2)

    def monitor_door_status(self, _dt):
        """
        Replace this with real GPIO read.
        0 = closed, 1 = open
        """
        door_state = self._simulate_door_state()

        if door_state != self._last_door_state:
            if door_state == 1:
                self.on_door_opened()
            else:
                self.on_door_closed()

            self._last_door_state = door_state

    def _simulate_door_state(self):
        """
        TEMP: Replace with GPIO subscriber value
        """
        return 1  # simulate door open

    # -----------------------------------------------------
    # DOOR EVENTS
    # -----------------------------------------------------
    def on_door_opened(self):
        print("[DOOR] OPENED")

        self.door_timer = 0
        self.progress_value = 0.0
        self.time_remaining = str(self.max_door_time)

        if self._can_poll_event is None:
            self._can_poll_event = Clock.schedule_interval(
                self.poll_can_events, 0.2
            )

        if self._door_timer_event is None:
            self._door_timer_event = Clock.schedule_interval(
                self._door_timer_tick, 1
            )

    def on_door_closed(self):
        print("[DOOR] CLOSED")

        if self._can_poll_event:
            self._can_poll_event.cancel()
            self._can_poll_event = None

        if self._door_timer_event:
            self._door_timer_event.cancel()
            self._door_timer_event = None

        print(f"[DOOR] Open duration: {self.door_timer}s")

    # -----------------------------------------------------
    def _door_timer_tick(self, dt):
        self.door_timer += 1

        remaining = max(self.max_door_time - self.door_timer, 0)
        self.time_remaining = str(remaining)

        self.progress_value = min(
            self.door_timer / float(self.max_door_time),
            1.0
        )

        if self.door_timer >= self.max_door_time:
            self.on_door_closed()

    # -----------------------------------------------------
    # CAN POLLING
    # -----------------------------------------------------
    def poll_can_events(self, _dt):
        ams_can = self.manager.ams_can

        if ams_can.key_taken_event:
            set_key_status_by_peg_id(ams_can.key_taken_id, 1)
            self.reload_keys_from_db()
            self.update_key_widgets()
            ams_can.key_taken_event = False

        if ams_can.key_inserted_event:
            set_key_status_by_peg_id(ams_can.key_inserted_id, 0)
            self.reload_keys_from_db()
            self.update_key_widgets()
            ams_can.key_inserted_event = False

    # -----------------------------------------------------
    def reload_keys_from_db(self):
        keys = get_keys_for_activity(self.activity_info["id"])
        self.keys_data = keys

    def populate_keys(self):
        grid = self.ids.key_grid
        grid.clear_widgets()
        self.key_widgets.clear()

        for item in self.keys_data:
            widget = KeyItem(
                key_id=str(item["id"]),
                key_name=item["name"],
                dashboard=self
            )
            self.key_widgets[str(item["id"])] = widget
            grid.add_widget(widget)

        self.update_key_widgets()

    def update_key_widgets(self):
        for item in self.keys_data:
            widget = self.key_widgets.get(str(item["id"]))
            if widget:
                widget.set_status("IN" if item["status"] == 0 else "OUT")

    def unlock_activity_keys(self):
        ams_can = self.manager.ams_can
        for item in self.keys_data:
            ams_can.unlock_single_key(item["strip"], item["position"])

    # -----------------------------------------------------
    def go_back(self):
        print("[UI] ◀ Back → Activity")
        self.on_door_closed()
        self.manager.current = "activity"

    def open_done_page(self, key_name, status, key_id):
        self.manager.current = "activity_done"
