from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from kivy.clock import Clock

from components.base_screen import BaseScreen
from db import get_keys_for_activity, set_key_status_by_peg_id
from test import AMS_CAN


# --------------------------------------------------
# Key Item Widget
# --------------------------------------------------
class KeyItem(ButtonBehavior, BoxLayout):
    key_name = StringProperty("")
    status = StringProperty("")   # IN / OUT
    status_color = ListProperty([0, 1, 0, 1])
    dashboard = ObjectProperty(None)
    key_id = StringProperty("")

    def on_status(self, *_):
        self.status_color = [0, 1, 0, 1] if self.status == "IN" else [1, 0, 0, 1]

    def on_release(self):
        if self.dashboard:
            self.dashboard.open_done_page(
                self.key_name, self.status, self.key_id
            )


# --------------------------------------------------
# Dashboard Screen
# --------------------------------------------------
class KeyDashboardScreen(BaseScreen):

    activity_code = StringProperty("")
    activity_name = StringProperty("")
    time_remaining = StringProperty("15")
    keys_data = ListProperty([])

    def on_enter(self, *args):
        self.activity_info = getattr(self.manager, "activity_info", None)

        if self.activity_info:
            self.activity_code = self.activity_info.get("code", "")
            self.activity_name = self.activity_info.get("name", "")
            self.time_remaining = str(self.activity_info.get("time_limit", 15))
            self.refresh_keys_from_db()
        else:
            self.keys_data = []
            self.populate_keys()

        if not hasattr(self.manager, "ams_can"):
            self.manager.ams_can = AMS_CAN()

        Clock.schedule_interval(self.check_can_events, 0.2)
        self.unlock_all_displayed_keys()

    def on_leave(self, *args):
        Clock.unschedule(self.check_can_events)

    # --------------------------------------------------
    # DB → UI
    # --------------------------------------------------
    def refresh_keys_from_db(self):
        activity_id = self.activity_info.get("id")
        keys = get_keys_for_activity(activity_id)

        self.keys_data = []
        for k in keys:
            self.keys_data.append({
                "key_id": str(k["id"]),
                "key_name": k["name"],
                "status": k["status"],
                "strip": k["strip"],
                "position": k["position"],
            })

        self.populate_keys()

    def populate_keys(self):
        grid = self.ids.key_grid
        grid.clear_widgets()

        for item in self.keys_data:
            widget = KeyItem(
                key_id=item["key_id"],
                key_name=item["key_name"],
                status="IN" if item["status"] == 0 else "OUT",
                dashboard=self
            )
            grid.add_widget(widget)

    # --------------------------------------------------
    # CAN → DB → UI (EXPLICIT STATE)
    # --------------------------------------------------
    def check_can_events(self, dt):
        ams_can = self.manager.ams_can

        # KEY TAKEN → OUT
        if ams_can.key_taken_event:
            peg_id = ams_can.key_taken_id
            print(f"[CAN] 🔴 KEY TAKEN peg_id={peg_id}")

            set_key_status_by_peg_id(peg_id, 1)
            self.refresh_keys_from_db()

            ams_can.key_taken_event = False

        # KEY INSERTED → IN
        if ams_can.key_inserted_event:
            peg_id = ams_can.key_inserted_id
            print(f"[CAN] 🟢 KEY INSERTED peg_id={peg_id}")

            set_key_status_by_peg_id(peg_id, 0)
            self.refresh_keys_from_db()

            ams_can.key_inserted_event = False

    # --------------------------------------------------
    # Unlock keys on screen enter
    # --------------------------------------------------
    def unlock_all_displayed_keys(self):
        ams_can = self.manager.ams_can

        keys = []
        for k in self.keys_data:
            if k["strip"] and k["position"]:
                keys.append({
                    "strip": int(k["strip"]),
                    "position": int(k["position"]),
                    "name": k["key_name"]
                })

        if keys:
            ams_can.unlock_keys_batch(keys)

    # --------------------------------------------------
    # Navigation
    # --------------------------------------------------
    def open_done_page(self, key_name, status, key_id):
        self.manager.selected_key_id = key_id
        self.manager.selected_key_name = key_name

        done = self.manager.get_screen("activity_done")
        done.retrieved_text = f"{key_name} ({status})"
        done.returned_text = ""

        self.manager.transition.direction = "left"
        self.manager.current = "activity_done"

    def go_back(self):
        self.manager.transition.direction = "right"
        self.manager.current = "activity_code"
