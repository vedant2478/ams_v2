# pages/key_dashboard/key_dashboard.py

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from kivy.clock import Clock

from components.base_screen import BaseScreen
from db import get_keys_for_activity, toggle_key_status_and_get_position
from test import AMS_CAN   # adjust if filename differs


# =========================
# KEY ITEM WIDGET
# =========================
class KeyItem(ButtonBehavior, BoxLayout):
    key_name = StringProperty("")
    status = StringProperty("")  # IN / OUT
    status_color = ListProperty([0, 1, 0, 1])
    dashboard = ObjectProperty(None)
    key_id = StringProperty("")

    def on_status(self, *_):
        if isinstance(self.status, int):
            self.status_color = [0, 1, 0, 1] if self.status == 0 else [1, 0, 0, 1]
        else:
            self.status_color = (
                [0, 1, 0, 1] if self.status.upper() == "IN" else [1, 0, 0, 1]
            )

    def on_release(self):
        if self.dashboard:
            self.dashboard.open_done_page(
                self.key_name,
                self.status,
                self.key_id
            )


# =========================
# KEY DASHBOARD SCREEN
# =========================
class KeyDashboardScreen(BaseScreen):

    activity_code = StringProperty("")
    activity_name = StringProperty("")
    time_remaining = StringProperty("15")
    keys_data = ListProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.keys_data = []

    # =========================
    # SCREEN ENTRY
    # =========================
    def on_enter(self, *args):
        self.activity_info = getattr(self.manager, 'activity_info', None)
        self.card_info = getattr(self.manager, 'card_info', None)

        if self.activity_info:
            self.activity_code = self.activity_info.get('code', '')
            self.activity_name = self.activity_info.get('name', '')
            self.time_remaining = str(self.activity_info.get('time_limit', 15))

            activity_id = self.activity_info.get('id')
            keys = get_keys_for_activity(activity_id)

            self.keys_data = []
            for key in keys:
                self.keys_data.append({
                    "key_id": str(key['id']),
                    "key_name": key['name'],
                    "status": key['status'],  # 0 = IN, 1 = OUT
                    "location": key.get('location', ''),
                    "description": key.get('description', ''),
                    "strip": key.get('strip'),
                    "position": key.get('position'),
                })
        else:
            self.activity_code = "N/A"
            self.activity_name = "No Activity"
            self.keys_data = []

        self.populate_keys()
        self.unlock_all_displayed_keys()

        # 🔴 START CAN MONITOR
        Clock.schedule_interval(self.check_can_events, 0.2)

    def on_leave(self, *args):
        Clock.unschedule(self.check_can_events)

    # =========================
    # UI POPULATION
    # =========================
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

    # =========================
    # UNLOCK KEYS VIA CAN
    # =========================
    def unlock_all_displayed_keys(self):
        if not self.keys_data:
            return

        if not hasattr(self.manager, "ams_can") or self.manager.ams_can is None:
            self.manager.ams_can = AMS_CAN()

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
            ams_can.unlock_keys_batch(keys_to_unlock)

    # =========================
    # CAN → DB → UI SYNC
    # =========================
    def check_can_events(self, dt):
        if not hasattr(self.manager, "ams_can"):
            return

        ams_can = self.manager.ams_can

        # -------- KEY TAKEN (OUT) --------
        if ams_can.key_taken_event:
            key_id = ams_can.key_taken_id
            print(f"[CAN] Key TAKEN → {key_id}")

            db_result = toggle_key_status_and_get_position(key_id)

            if db_result:
                for item in self.keys_data:
                    if str(item["key_id"]) == str(key_id):
                        item["status"] = 1  # OUT
                        break
                self.populate_keys()

            ams_can.key_taken_event = False

        # -------- KEY INSERTED (IN) --------
        if ams_can.key_inserted_event:
            key_id = ams_can.key_inserted_id
            print(f"[CAN] Key INSERTED → {key_id}")

            db_result = toggle_key_status_and_get_position(key_id)

            if db_result:
                for item in self.keys_data:
                    if str(item["key_id"]) == str(key_id):
                        item["status"] = 0  # IN
                        break
                self.populate_keys()

            ams_can.key_inserted_event = False

    # =========================
    # NAVIGATION
    # =========================
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
