from time import sleep
from threading import Thread

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
    status = StringProperty("IN")          # IN / OUT
    status_color = ListProperty([0, 1, 0, 1])
    dashboard = ObjectProperty(None)

    def set_status(self, status):
        self.status = status
        self.status_color = [0, 1, 0, 1] if status == "IN" else [1, 0, 0, 1]

    def on_release(self):
        if self.dashboard:
            self.dashboard.open_done_page(
                self.key_name, self.status, self.key_id
            )


# =========================================================
# SCREEN
# =========================================================
class KeyDashboardScreen(BaseScreen):

    activity_code = StringProperty("")
    activity_name = StringProperty("")
    time_remaining = StringProperty("15")

    keys_data = ListProperty()
    is_loading = BooleanProperty(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.keys_data = []
        self._can_poll_event = None

    # -----------------------------------------------------
    # ENTER
    # -----------------------------------------------------
    def on_enter(self, *args):
        print("[UI] ▶ Entered KeyDashboardScreen")
        self.is_loading = True

        self.activity_info = getattr(self.manager, "activity_info", None)
        if not self.activity_info:
            print("[UI] ❌ No activity info")
            self.is_loading = False
            return

        self.activity_code = self.activity_info.get("code", "")
        self.activity_name = self.activity_info.get("name", "")
        self.time_remaining = str(self.activity_info.get("time_limit", 15))

        # Run heavy CAN init in background
        Thread(target=self._initialize_dashboard, daemon=True).start()

    # -----------------------------------------------------
    # BACKGROUND INIT
    # -----------------------------------------------------
    def _initialize_dashboard(self):
        try:
            if not hasattr(self.manager, "ams_can") or self.manager.ams_can is None:
                print("[CAN] Creating AMS_CAN instance")
                self.manager.ams_can = AMS_CAN()
                sleep(2)

            # Lock everything first (safety)
            self._lock_all_keys_safe()

            # Load DB
            self.reload_keys_from_db()

            # Unlock only allowed keys
            self.unlock_activity_keys()

            # Start CAN polling on UI thread
            Clock.schedule_once(self._start_can_poll, 0)

        except Exception as e:
            print("[ERROR] Dashboard init failed:", e)

        Clock.schedule_once(self._finish_loading, 0)

    def _finish_loading(self, _dt):
        self.populate_keys()
        self.is_loading = False

    # -----------------------------------------------------
    # SAFE CAN OPS
    # -----------------------------------------------------
    def _lock_all_keys_safe(self):
        try:
            ams_can = self.manager.ams_can
            for strip in ams_can.key_lists or [1]:
                ams_can.lock_all_positions(strip)
                ams_can.set_all_LED_OFF(strip)
        except Exception as e:
            print("[CAN][WARN] Lock all failed:", e)

    # -----------------------------------------------------
    # DATABASE
    # -----------------------------------------------------
    def reload_keys_from_db(self):
        activity_id = self.activity_info.get("id")
        keys = get_keys_for_activity(activity_id)

        self.keys_data = []
        print(f"[DB] Loaded {len(keys)} keys")

        for key in keys:
            self.keys_data.append({
                "key_id": str(key["id"]),
                "key_name": key["name"],
                "status": key["status"],   # 0 / 1
                "strip": key.get("strip"),
                "position": key.get("position"),
            })

    # -----------------------------------------------------
    # UI
    # -----------------------------------------------------
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

    # -----------------------------------------------------
    # UNLOCK ACTIVITY KEYS ONLY
    # -----------------------------------------------------
    def unlock_activity_keys(self):
        try:
            ams_can = self.manager.ams_can
            for item in self.keys_data:
                if item["strip"] and item["position"]:
                    ams_can.unlock_single_key(
                        int(item["strip"]), int(item["position"])
                    )
        except Exception as e:
            print("[CAN][WARN] Unlock failed:", e)

    # -----------------------------------------------------
    # CAN EVENTS
    # -----------------------------------------------------
    def _start_can_poll(self, _dt):
        if self._can_poll_event is None:
            self._can_poll_event = Clock.schedule_interval(
                self.poll_can_events, 0.2
            )

    def poll_can_events(self, _dt):
        ams_can = self.manager.ams_can

        if ams_can.key_taken_event:
            set_key_status_by_peg_id(ams_can.key_taken_id, 1)
            self.reload_keys_from_db()
            self.populate_keys()
            ams_can.key_taken_event = False

        if ams_can.key_inserted_event:
            set_key_status_by_peg_id(ams_can.key_inserted_id, 0)
            self.reload_keys_from_db()
            self.populate_keys()
            ams_can.key_inserted_event = False

    # -----------------------------------------------------
    # BACK NAVIGATION
    # -----------------------------------------------------
    def go_back(self):
        print("[UI] ◀ Back pressed")

        if self._can_poll_event:
            self._can_poll_event.cancel()
            self._can_poll_event = None

        try:
            ams_can = self.manager.ams_can
            for strip in ams_can.key_lists or [1]:
                ams_can.unlock_all_positions(strip)
                ams_can.set_all_LED_OFF(strip)
        except Exception as e:
            print("[CAN][WARN] Cleanup failed:", e)

        self.manager.transition.direction = "right"
        self.manager.current = "activity_code"

    def open_done_page(self, key_name, status, key_id):
        self.manager.selected_key_id = key_id
        self.manager.selected_key_name = key_name
        self.manager.current = "activity"
