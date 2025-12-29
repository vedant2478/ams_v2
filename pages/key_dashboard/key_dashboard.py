from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from kivy.clock import Clock

from components.base_screen import BaseScreen
from db import get_keys_for_activity, toggle_key_status_and_get_position
from test import AMS_CAN


# ---------------------------
# Key Widget
# ---------------------------
class KeyItem(ButtonBehavior, BoxLayout):
    key_id = StringProperty("")
    key_name = StringProperty("")
    status = StringProperty("IN")
    status_color = ListProperty([0, 1, 0, 1])  # default GREEN
    dashboard = ObjectProperty(None)

    def set_status(self, status):
        """Explicitly set status and color (NO on_status usage)"""
        self.status = status
        if status == "IN":
            self.status_color = [0, 1, 0, 1]   # green
        else:
            self.status_color = [1, 0, 0, 1]   # red

    def on_release(self):
        if self.dashboard:
            self.dashboard.open_done_page(
                self.key_name, self.status, self.key_id
            )


# ---------------------------
# Dashboard Screen
# ---------------------------
class KeyDashboardScreen(BaseScreen):

    activity_code = StringProperty("")
    activity_name = StringProperty("")
    time_remaining = StringProperty("15")
    keys_data = ListProperty([])

    def on_enter(self, *args):
        self.activity_info = getattr(self.manager, "activity_info", None)

        if not self.activity_info:
            self.keys_data = []
            self.populate_keys()
            return

        self.activity_code = self.activity_info.get("code", "")
        self.activity_name = self.activity_info.get("name", "")
        self.time_remaining = str(self.activity_info.get("time_limit", 15))

        self.reload_keys_from_db()
        self.populate_keys()
        self.unlock_all_displayed_keys()

        # Start CAN polling loop
        Clock.schedule_interval(self.poll_can_events, 0.3)

    def on_leave(self, *args):
        Clock.unschedule(self.poll_can_events)

    # ---------------------------
    # DATABASE + UI
    # ---------------------------
    def reload_keys_from_db(self):
        activity_id = self.activity_info.get("id")
        keys = get_keys_for_activity(activity_id)

        self.keys_data = []
        for key in keys:
            self.keys_data.append({
                "key_id": str(key["id"]),
                "key_name": key["name"],
                "status": "IN" if key["status"] == 0 else "OUT",
                "strip": key.get("strip"),
                "position": key.get("position"),
            })

    def populate_keys(self):
        grid = self.ids.key_grid
        grid.clear_widgets()

        for item in self.keys_data:
            widget = KeyItem(
                key_id=item["key_id"],
                key_name=item["key_name"],
                dashboard=self,
            )
            widget.set_status(item["status"])
            grid.add_widget(widget)

    # ---------------------------
    # CAN INTEGRATION
    # ---------------------------
    def unlock_all_displayed_keys(self):
        if not hasattr(self.manager, "ams_can") or self.manager.ams_can is None:
            self.manager.ams_can = AMS_CAN()

        ams_can = self.manager.ams_can

        for item in self.keys_data:
            if item["strip"] and item["position"]:
                ams_can.unlock_single_key(
                    int(item["strip"]),
                    int(item["position"])
                )

    def poll_can_events(self, _dt):
        ams_can = getattr(self.manager, "ams_can", None)
        if not ams_can:
            return

        # ---------------- KEY TAKEN ----------------
        if ams_can.key_taken_event:
            peg_id = ams_can.key_taken_id
            print(f"[CAN] 🔴 KEY TAKEN peg_id={peg_id}")

            updated = toggle_key_status_and_get_position(peg_id)
            if updated:
                print(f"[DB] ✅ Updated key_id={updated['id']} → OUT")

                self.reload_keys_from_db()
                self.populate_keys()

            ams_can.key_taken_event = False

        # ---------------- KEY INSERTED ----------------
        if ams_can.key_inserted_event:
            peg_id = ams_can.key_inserted_id
            print(f"[CAN] 🟢 KEY INSERTED peg_id={peg_id}")

            updated = toggle_key_status_and_get_position(peg_id)
            if updated:
                print(f"[DB] ✅ Updated key_id={updated['id']} → IN")

                self.reload_keys_from_db()
                self.populate_keys()

            ams_can.key_inserted_event = False

    # ---------------------------
    # NAVIGATION
    # ---------------------------
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
