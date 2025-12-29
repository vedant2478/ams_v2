from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from kivy.clock import Clock

from components.base_screen import BaseScreen
from db import get_keys_for_activity, set_key_status_by_peg_id
from test import AMS_CAN


# -------------------- UI ITEM --------------------
class KeyItem(ButtonBehavior, BoxLayout):
    key_id = StringProperty("")
    key_name = StringProperty("")
    status = StringProperty("IN")
    status_color = ListProperty([0, 1, 0, 1])
    dashboard = ObjectProperty(None)

    def set_status(self, status):
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


# -------------------- SCREEN --------------------
class KeyDashboardScreen(BaseScreen):

    activity_code = StringProperty("")
    activity_name = StringProperty("")
    time_remaining = StringProperty("15")
    keys_data = ListProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.keys_data = []
        self._can_poll_event = None

    # -------------------- ENTER --------------------
    def on_enter(self, *args):
        print("[UI] Entered KeyDashboardScreen")

        self.activity_info = getattr(self.manager, "activity_info", None)

        if not self.activity_info:
            print("[UI] ❌ No activity info")
            return

        self.activity_code = self.activity_info.get("code", "")
        self.activity_name = self.activity_info.get("name", "")
        self.time_remaining = str(self.activity_info.get("time_limit", 15))

        # Create CAN instance once
        if not hasattr(self.manager, "ams_can") or self.manager.ams_can is None:
            print("[CAN] Creating AMS_CAN instance")
            self.manager.ams_can = AMS_CAN()

        # Load keys from DB
        self.reload_keys_from_db()
        self.populate_keys()

        # Unlock keys
        self.unlock_all_displayed_keys()

        # START polling CAN
        if self._can_poll_event is None:
            self._can_poll_event = Clock.schedule_interval(
                self.poll_can_events, 0.2
            )

    # -------------------- EXIT --------------------
    def on_leave(self, *args):
        if self._can_poll_event:
            self._can_poll_event.cancel()
            self._can_poll_event = None

    # -------------------- DB --------------------
    def reload_keys_from_db(self):
        activity_id = self.activity_info.get("id")
        keys = get_keys_for_activity(activity_id)

        print(f"[DB] Loaded {len(keys)} keys")

        self.keys_data = []
        for key in keys:
            self.keys_data.append({
                "key_id": str(key["id"]),
                "key_name": key["name"],
                "status": key["status"],  # 0 IN, 1 OUT
                "strip": key.get("strip"),
                "position": key.get("position"),
            })

    # -------------------- UI --------------------
    def populate_keys(self):
        grid = self.ids.key_grid
        grid.clear_widgets()

        for item in self.keys_data:
            status_text = "IN" if item["status"] == 0 else "OUT"

            widget = KeyItem(
                key_id=item["key_id"],
                key_name=item["key_name"],
                dashboard=self
            )
            widget.set_status(status_text)

            grid.add_widget(widget)

    # -------------------- CAN POLL --------------------
    def poll_can_events(self, _dt):
        ams_can = self.manager.ams_can

        # 🔴 KEY TAKEN
        if ams_can.key_taken_event:
            peg_id = ams_can.key_taken_id
            print(f"[CAN] 🔴 KEY TAKEN peg_id={peg_id}")

            set_key_status_by_peg_id(peg_id, 1)  # OUT
            self.reload_keys_from_db()
            self.populate_keys()

            ams_can.key_taken_event = False

        # 🟢 KEY INSERTED
        if ams_can.key_inserted_event:
            peg_id = ams_can.key_inserted_id
            print(f"[CAN] 🟢 KEY INSERTED peg_id={peg_id}")

            set_key_status_by_peg_id(peg_id, 0)  # IN
            self.reload_keys_from_db()
            self.populate_keys()

            ams_can.key_inserted_event = False

    # -------------------- UNLOCK --------------------
    def unlock_all_displayed_keys(self):
        ams_can = self.manager.ams_can
        print(f"[CAN] Unlocking {len(self.keys_data)} keys")

        for item in self.keys_data:
            if item["strip"] and item["position"]:
                ams_can.unlock_single_key(
                    int(item["strip"]),
                    int(item["position"])
                )

    # -------------------- NAV --------------------
    def open_done_page(self, key_name, status, key_id):
        self.manager.selected_key_id = key_id
        self.manager.selected_key_name = key_name
        self.manager.current = "activity_done"
