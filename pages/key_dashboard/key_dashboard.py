from time import sleep
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty, ListProperty, ObjectProperty, BooleanProperty
from kivy.clock import Clock

from components.base_screen import BaseScreen
from db import get_keys_for_activity, set_key_status_by_peg_id
from test import AMS_CAN


# =========================================================
# UI ITEM
# =========================================================
class KeyItem(ButtonBehavior, BoxLayout):
    key_id = StringProperty("")
    key_name = StringProperty("")
    status = StringProperty("IN")        # drives TEXT
    status_color = ListProperty([0, 1, 0, 1])
    dashboard = ObjectProperty(None)

    def set_status(self, status: str):
        status = status.upper().strip()
        self.status = status

        if status == "IN":
            self.status_color = [0, 1, 0, 1]
        else:
            self.status_color = [1, 0, 0, 1]

    def on_release(self):
        if self.dashboard:
            self.dashboard.open_done_page(
                self.key_name,
                self.status,
                self.key_id
            )


# =========================================================
# SCREEN
# =========================================================
class KeyDashboardScreen(BaseScreen):

    activity_code = StringProperty("")
    activity_name = StringProperty("")
    time_remaining = StringProperty("15")

    loading = BooleanProperty(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.keys_data = []
        self.key_widgets = {}          # 🔑 IMPORTANT
        self._can_poll_event = None

    # -----------------------------------------------------
    # ENTER
    # -----------------------------------------------------
    def on_enter(self, *args):
        print("[UI] ▶ Entered KeyDashboardScreen")
        self.loading = True

        self.activity_info = getattr(self.manager, "activity_info", None)
        if not self.activity_info:
            return

        self.activity_code = self.activity_info.get("code", "")
        self.activity_name = self.activity_info.get("name", "")
        self.time_remaining = str(self.activity_info.get("time_limit", 15))

        if not hasattr(self.manager, "ams_can"):
            print("[CAN] Creating AMS_CAN")
            self.manager.ams_can = AMS_CAN()
            Clock.schedule_once(self._finish_init, 0)

    def _finish_init(self, _dt):
        self.reload_keys_from_db()
        self.populate_keys()
        self.unlock_activity_keys()

        self.loading = False

        if not self._can_poll_event:
            self._can_poll_event = Clock.schedule_interval(
                self.poll_can_events, 0.2
            )

    def on_leave(self, *args):
        if self._can_poll_event:
            self._can_poll_event.cancel()
            self._can_poll_event = None

    # =====================================================
    # DATABASE
    # =====================================================
    def reload_keys_from_db(self):
        activity_id = self.activity_info.get("id")
        keys = get_keys_for_activity(activity_id)

        self.keys_data = keys

        print("[DB] Loaded keys:")
        for k in keys:
            print(f" - {k['name']} → {'IN' if k['status']==0 else 'OUT'}")

    # =====================================================
    # UI RENDER (ONCE)
    # =====================================================
    def populate_keys(self):
        grid = self.ids.key_grid
        grid.clear_widgets()
        self.key_widgets.clear()

        for item in self.keys_data:
            status_text = "IN" if item["status"] == 0 else "OUT"

            widget = KeyItem(
                key_id=str(item["id"]),
                key_name=item["name"],
                dashboard=self
            )
            widget.set_status(status_text)

            self.key_widgets[str(item["id"])] = widget
            grid.add_widget(widget)

    # =====================================================
    # UPDATE UI WITHOUT REBUILDING
    # =====================================================
    def update_key_ui(self, key_id, status_int):
        widget = self.key_widgets.get(str(key_id))
        if not widget:
            return

        widget.set_status("IN" if status_int == 0 else "OUT")

    # =====================================================
    # CAN EVENTS
    # =====================================================
    def poll_can_events(self, _dt):
        ams_can = self.manager.ams_can

        if ams_can.key_taken_event:
            peg_id = ams_can.key_taken_id
            key_id = set_key_status_by_peg_id(peg_id, 1)

            if key_id:
                self.update_key_ui(key_id, 1)

            ams_can.key_taken_event = False

        if ams_can.key_inserted_event:
            peg_id = ams_can.key_inserted_id
            key_id = set_key_status_by_peg_id(peg_id, 0)

            if key_id:
                self.update_key_ui(key_id, 0)

            ams_can.key_inserted_event = False

    # =====================================================
    # UNLOCK KEYS
    # =====================================================
    def unlock_activity_keys(self):
        ams_can = self.manager.ams_can
        for item in self.keys_data:
            if item["strip"] and item["position"]:
                ams_can.unlock_single_key(
                    int(item["strip"]),
                    int(item["position"])
                )

    # =====================================================
    # BACK BUTTON
    # =====================================================
    def go_back(self):
        print("[UI] Going back → locking all keys")

        if hasattr(self.manager, "ams_can"):
            ams_can = self.manager.ams_can
            for strip in ams_can.key_lists:
                ams_can.lock_all_positions(strip)
                ams_can.set_all_LED_OFF(strip)

        self.manager.current = "previous_screen"

    # =====================================================
    # NAV
    # =====================================================
    def open_done_page(self, key_name, status, key_id):
        self.manager.selected_key_id = key_id
        self.manager.selected_key_name = key_name
        self.manager.current = "activity"
