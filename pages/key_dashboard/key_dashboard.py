# pages/key_dashboard/key_dashboard.py

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from kivy.clock import Clock

from components.base_screen import BaseScreen
from db import get_keys_for_activity, set_key_status
from test import AMS_CAN


# ------------------------------
# UI COMPONENT: SINGLE KEY ITEM
# ------------------------------
class KeyItem(ButtonBehavior, BoxLayout):
    key_name = StringProperty("")
    status = StringProperty("")   # "IN" / "OUT"
    status_color = ListProperty([0, 1, 0, 1])
    dashboard = ObjectProperty(None)
    key_id = StringProperty("")

    def on_status(self, *_):
        # Status strictly controlled by DB
        if self.status == "IN":
            self.status_color = [0, 1, 0, 1]   # green
        else:
            self.status_color = [1, 0, 0, 1]   # red

    def on_release(self):
        if self.dashboard:
            self.dashboard.open_done_page(
                self.key_name, self.status, self.key_id
            )


# ------------------------------
# MAIN DASHBOARD SCREEN
# ------------------------------
class KeyDashboardScreen(BaseScreen):

    activity_code = StringProperty("")
    activity_name = StringProperty("")
    time_remaining = StringProperty("15")
    keys_data = ListProperty([])

    def on_enter(self, *args):
        print("[UI] Entered KeyDashboardScreen")

        self.activity_info = getattr(self.manager, "activity_info", None)

        if not self.activity_info:
            print("⚠️ No activity info")
            return

        self.activity_code = self.activity_info["code"]
        self.activity_name = self.activity_info["name"]
        self.time_remaining = str(self.activity_info.get("time_limit", 15))

        # Create shared AMS_CAN instance once
        if not hasattr(self.manager, "ams_can") or self.manager.ams_can is None:
            print("[CAN] Creating AMS_CAN instance")
            self.manager.ams_can = AMS_CAN()

        self.reload_keys_from_db()
        self.populate_keys()
        self.unlock_all_displayed_keys()

        # Poll CAN events continuously
        Clock.schedule_interval(self.poll_can_events, 0.2)

    def on_leave(self, *args):
        Clock.unschedule(self.poll_can_events)

    # ------------------------------
    # LOAD DATA FROM DATABASE
    # ------------------------------
    def reload_keys_from_db(self):
        activity_id = self.activity_info["id"]
        keys = get_keys_for_activity(activity_id)

        self.keys_data = []
        for key in keys:
            self.keys_data.append({
                "key_id": str(key["id"]),
                "key_name": key["name"],
                "status": key["status"],  # 0=IN, 1=OUT
                "strip": key["strip"],
                "position": key["position"],
            })

        print(f"[DB] Loaded {len(self.keys_data)} keys")

    # ------------------------------
    # POPULATE UI FROM keys_data
    # ------------------------------
    def populate_keys(self):
        grid = self.ids.key_grid
        grid.clear_widgets()

        for item in self.keys_data:
            status_text = "IN" if item["status"] == 0 else "OUT"

            key_widget = KeyItem(
                key_id=item["key_id"],
                key_name=item["key_name"],
                status=status_text,
                dashboard=self,
            )
            grid.add_widget(key_widget)

    # ------------------------------
    # UNLOCK KEYS ON SCREEN LOAD
    # ------------------------------
    def unlock_all_displayed_keys(self):
        ams_can = self.manager.ams_can
        keys_to_unlock = []

        for item in self.keys_data:
            if item["strip"] and item["position"]:
                keys_to_unlock.append({
                    "strip": int(item["strip"]),
                    "position": int(item["position"]),
                    "name": item["key_name"]
                })

        if keys_to_unlock:
            print(f"[CAN] Unlocking {len(keys_to_unlock)} keys")
            ams_can.unlock_keys_batch(keys_to_unlock)

    # ------------------------------
    # POLL CAN EVENTS (REAL TIME)
    # ------------------------------
    def poll_can_events(self, _dt):
        ams_can = self.manager.ams_can

        # 🔴 KEY TAKEN → OUT
        if ams_can.key_taken_event:
            peg_id = ams_can.key_taken_id
            print(f"[CAN] 🔴 KEY TAKEN peg_id={peg_id}")

            set_key_status(peg_id, 1)   # SET → OUT

            self.reload_keys_from_db()
            self.populate_keys()

            ams_can.key_taken_event = False

        # 🟢 KEY INSERTED → IN
        if ams_can.key_inserted_event:
            peg_id = ams_can.key_inserted_id
            print(f"[CAN] 🟢 KEY INSERTED peg_id={peg_id}")

            set_key_status(peg_id, 0)   # SET → IN

            self.reload_keys_from_db()
            self.populate_keys()

            ams_can.key_inserted_event = False

    # ------------------------------
    # NAVIGATION
    # ------------------------------
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
