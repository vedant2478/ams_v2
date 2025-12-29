# pages/key_dashboard/key_dashboard.py

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from kivy.clock import Clock

from components.base_screen import BaseScreen
from db import get_keys_for_activity, set_key_status_by_peg_id
from test import AMS_CAN


# -------------------------
# Individual Key Widget
# -------------------------
class KeyItem(ButtonBehavior, BoxLayout):
    key_name = StringProperty("")
    status = StringProperty("IN")   # "IN" or "OUT"
    status_color = ListProperty([0, 1, 0, 1])  # green default
    dashboard = ObjectProperty(None)
    key_id = StringProperty("")

    def on_status(self, *_):
        """Automatically update color when status changes"""
        if self.status.upper() == "IN":
            self.status_color = [0, 1, 0, 1]   # Green
        else:
            self.status_color = [1, 0, 0, 1]   # Red

    def on_release(self):
        if self.dashboard:
            self.dashboard.open_done_page(
                self.key_name, self.status, self.key_id
            )


# -------------------------
# Key Dashboard Screen
# -------------------------
class KeyDashboardScreen(BaseScreen):

    activity_code = StringProperty("")
    activity_name = StringProperty("")
    time_remaining = StringProperty("15")
    keys_data = ListProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.keys_data = []
        self.key_widgets = {}  # 🔥 key_id → KeyItem reference

    # -------------------------
    # Screen lifecycle
    # -------------------------
    def on_enter(self, *args):
        """Called when screen becomes visible"""

        self.activity_info = getattr(self.manager, "activity_info", None)

        if not self.activity_info:
            print("⚠️ No activity info found")
            return

        self.activity_code = self.activity_info.get("code", "")
        self.activity_name = self.activity_info.get("name", "")
        self.time_remaining = str(self.activity_info.get("time_limit", 15))

        # Load keys from DB
        self.load_keys_from_db()

        # Unlock keys physically
        self.unlock_all_displayed_keys()

        # Start CAN polling loop (10 times/sec)
        Clock.schedule_interval(self.check_can_events, 0.1)

    def on_leave(self, *args):
        """Stop polling when screen exits"""
        Clock.unschedule(self.check_can_events)

    # -------------------------
    # Load + populate UI
    # -------------------------
    def load_keys_from_db(self):
        activity_id = self.activity_info["id"]
        keys = get_keys_for_activity(activity_id)

        self.keys_data = []
        for key in keys:
            self.keys_data.append({
                "key_id": str(key["id"]),
                "key_name": key["name"],
                "status": key["status"],  # 0 IN / 1 OUT
                "strip": key.get("strip"),
                "position": key.get("position"),
            })

        self.populate_keys()

    def populate_keys(self):
        grid = self.ids.key_grid
        grid.clear_widgets()
        self.key_widgets.clear()

        for item in self.keys_data:
            status_text = "IN" if item["status"] == 0 else "OUT"

            widget = KeyItem(
                key_id=item["key_id"],
                key_name=item["key_name"],
                status=status_text,
                dashboard=self,
            )

            # 🔥 SAVE REFERENCE FOR REAL-TIME UPDATE
            self.key_widgets[item["key_id"]] = widget
            grid.add_widget(widget)

    # -------------------------
    # CAN event polling
    # -------------------------
    def check_can_events(self, dt):
        if not hasattr(self.manager, "ams_can"):
            return

        ams_can = self.manager.ams_can

        # -------- KEY TAKEN --------
        if ams_can.key_taken_event:
            peg_id = ams_can.key_taken_id
            print(f"[CAN] 🔴 KEY TAKEN peg_id={peg_id}")

            key_id = set_key_status_by_peg_id(peg_id, 1)  # OUT

            if key_id:
                widget = self.key_widgets.get(str(key_id))
                if widget:
                    widget.status = "OUT"   # 🔥 UI UPDATE

            ams_can.key_taken_event = False

        # -------- KEY INSERTED --------
        if ams_can.key_inserted_event:
            peg_id = ams_can.key_inserted_id
            print(f"[CAN] 🟢 KEY INSERTED peg_id={peg_id}")

            key_id = set_key_status_by_peg_id(peg_id, 0)  # IN

            if key_id:
                widget = self.key_widgets.get(str(key_id))
                if widget:
                    widget.status = "IN"    # 🔥 UI UPDATE

            ams_can.key_inserted_event = False

    # -------------------------
    # Unlock hardware keys
    # -------------------------
    def unlock_all_displayed_keys(self):
        if not hasattr(self.manager, "ams_can"):
            print("Creating AMS_CAN instance")
            self.manager.ams_can = AMS_CAN()

        ams_can = self.manager.ams_can

        for item in self.keys_data:
            strip = item.get("strip")
            pos = item.get("position")
            if strip and pos:
                ams_can.unlock_single_key(int(strip), int(pos))

    # -------------------------
    # Navigation
    # -------------------------
    def go_back(self):
        self.manager.transition.direction = "right"
        self.manager.current = "activity_code"

    def open_done_page(self, key_name, status, key_id):
        self.manager.selected_key_id = key_id
        self.manager.selected_key_name = key_name

        done = self.manager.get_screen("activity_done")
        done.retrieved_text = f"{key_name} ({status})"
        done.returned_text = ""

        self.manager.transition.direction = "left"
        self.manager.current = "activity_done"
