from time import sleep
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from kivy.clock import Clock
from csi_ams.utils.commons import read_limit_switch , LIMIT_SWITCH
import mraa
import subprocess
from components.base_screen import BaseScreen
from db import get_keys_for_activity, set_key_status_by_peg_id
from test import AMS_CAN


# =========================================================
# KEY ITEM (UI COMPONENT)
# =========================================================
class KeyItem(ButtonBehavior, BoxLayout):
    key_id = StringProperty("")
    key_name = StringProperty("")
    status_text = StringProperty("IN")     # <-- BOUND TO KV
    status_color = ListProperty([0, 1, 0, 1])
    dashboard = ObjectProperty(None)

    def set_status(self, status: str):
        """
        This is the ONLY method that updates UI state.
        KV is bound to status_text and status_color.
        """
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
    time_remaining = StringProperty("15")

    keys_data = ListProperty([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.key_widgets = {}          # key_id -> KeyItem
        self._can_poll_event = None
        self._last_door_state = None

    # -----------------------------------------------------
    # SCREEN ENTER
    # -----------------------------------------------------

    def on_enter(self, *args):
        print("\n[UI] ▶ Entered KeyDashboardScreen")

        self.activity_info = getattr(self.manager, "activity_info", None)
        if not self.activity_info:
            print("[UI] ❌ No activity info")
            return

        self.activity_code = self.activity_info.get("code", "")
        self.activity_name = self.activity_info.get("name", "")
        self.time_remaining = str(self.activity_info.get("time_limit", 15))

        # CAN init
        if not hasattr(self.manager, "ams_can") or self.manager.ams_can is None:
            print("[CAN] Creating AMS_CAN instance")
            self.manager.ams_can = AMS_CAN()
            self._setup_can_and_lock_all()

        # DB → UI
        self.reload_keys_from_db()
        self.populate_keys()

        # Unlock activity keys
        self.unlock_activity_keys()

        # 🔥 CALL HARDWARE SCRIPT (ROOT)
        try:
            subprocess.Popen(
                ["sudo", "python3", "solenoid.py","1"],
                cwd="/home/rock/Desktop/ams_v2"
            )
            print("[HW] Solenoid triggered")
        except Exception as e:
            print("[HW][ERROR]", e)

        # CAN polling
        if self._can_poll_event is None:
            self._can_poll_event = Clock.schedule_interval(
                self.poll_can_events, 0.2
            )

    # -----------------------------------------------------
    # TRACK DOOR STATE
    # ----------------------------------------------------- 
    def monitor_door_status(self):
        try:
            door_status = read_limit_switch(LIMIT_SWITCH)
        except Exception as e:
            print("[DOOR][ERROR]", e)
            return

        # door_status: 1 = OPEN, 0 = CLOSED
        if self._last_door_state is None:
            self._last_door_state = door_status
            print("[DOOR] Initial:", "OPEN" if door_status else "CLOSED")
            return

        if door_status != self._last_door_state:
            if door_status == 1:
                print("[DOOR] 🚪 OPEN")
            else:
                print("[DOOR] 🔒 CLOSED")

            self._last_door_state = door_status

   


    # -----------------------------------------------------
    # SCREEN EXIT
    # -----------------------------------------------------
    def on_leave(self, *args):
        if self._can_poll_event:
            self._can_poll_event.cancel()
            self._can_poll_event = None

    # -----------------------------------------------------
    # BACK BUTTON
    # -----------------------------------------------------
    def go_back(self):
        print("[UI] ◀ Back pressed → unlocking all keys")

        try:
            ams_can = self.manager.ams_can
            for strip_id in ams_can.key_lists or [1, 2]:
                ams_can.unlock_all_positions(strip_id)
                ams_can.set_all_LED_OFF(strip_id)
        except Exception as e:
            print("[WARN] CAN cleanup failed:", e)

        self.manager.transition.direction = "right"
        self.manager.current = "activity"

    # =====================================================
    # CAN INITIALIZATION
    # =====================================================
    def _setup_can_and_lock_all(self):
        ams_can = self.manager.ams_can

        print("[CAN][INIT] Waiting for CAN boot…")
        sleep(3)

        print("[CAN][SECURITY] Locking ALL keys")
        for strip_id in ams_can.key_lists or [1, 2]:
            ams_can.lock_all_positions(strip_id)
            ams_can.set_all_LED_OFF(strip_id)

    # =====================================================
    # DATABASE LOAD
    # =====================================================
    def reload_keys_from_db(self):
        activity_id = self.activity_info.get("id")
        keys = get_keys_for_activity(activity_id)

        print(f"\n[DB] Loaded {len(keys)} keys")

        self.keys_data = []
        for key in keys:
            self.keys_data.append({
                "key_id": str(key["id"]),
                "key_name": key["name"],
                "status": key["status"],   # 0 = IN, 1 = OUT
                "strip": key.get("strip"),
                "position": key.get("position"),
            })

    # =====================================================
    # UI BUILD (ONCE)
    # =====================================================
    def populate_keys(self):
        grid = self.ids.key_grid

        if not self.key_widgets:
            grid.clear_widgets()

            for item in self.keys_data:
                widget = KeyItem(
                    key_id=item["key_id"],
                    key_name=item["key_name"],
                    dashboard=self
                )
                self.key_widgets[item["key_id"]] = widget
                grid.add_widget(widget)

        self.update_key_widgets()

    # =====================================================
    # UI UPDATE (NO REBUILD)
    # =====================================================
    def update_key_widgets(self):
        for item in self.keys_data:
            widget = self.key_widgets.get(item["key_id"])
            if not widget:
                continue

            status_text = "IN" if item["status"] == 0 else "OUT"
            widget.set_status(status_text)

            print(f"[UI] {widget.key_name} → {status_text}")

    # =====================================================
    # UNLOCK ACTIVITY KEYS
    # =====================================================
    def unlock_activity_keys(self):
        ams_can = self.manager.ams_can
        print(f"[CAN] 🔓 Unlocking {len(self.keys_data)} keys")

        for item in self.keys_data:
            if item["strip"] and item["position"]:
                ams_can.unlock_single_key(
                    int(item["strip"]),
                    int(item["position"])
                )

    # =====================================================
    # CAN EVENTS (REALTIME)
    # =====================================================
    def poll_can_events(self, _dt):
        ams_can = self.manager.ams_can

        # 👀 Monitor door state
        self.monitor_door_status()

        # 🔴 KEY TAKEN
        if ams_can.key_taken_event:
            peg_id = ams_can.key_taken_id
            print(f"\n[CAN] 🔴 KEY TAKEN peg_id={peg_id}")

            set_key_status_by_peg_id(peg_id, 1)
            self.reload_keys_from_db()
            self.update_key_widgets()

            ams_can.key_taken_event = False

        # 🟢 KEY INSERTED
        if ams_can.key_inserted_event:
            peg_id = ams_can.key_inserted_id
            print(f"\n[CAN] 🟢 KEY INSERTED peg_id={peg_id}")

            set_key_status_by_peg_id(peg_id, 0)
            self.reload_keys_from_db()
            self.update_key_widgets()

            ams_can.key_inserted_event = False

    # -----------------------------------------------------
    def open_done_page(self, key_name, status, key_id):
        self.manager.selected_key_id = key_id
        self.manager.selected_key_name = key_name
        self.manager.current = "activity_done"
