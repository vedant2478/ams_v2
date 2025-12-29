from time import sleep

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty, ListProperty, ObjectProperty
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
    status = StringProperty("IN")        # IN / OUT
    status_color = ListProperty([0, 1, 0, 1])
    dashboard = ObjectProperty(None)

    def set_status(self, status):
        self.status = status
        self.status_color = [0, 1, 0, 1] if status == "IN" else [1, 0, 0, 1]

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
    keys_data = ListProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.keys_data = []
        self._can_poll_event = None

    # -----------------------------------------------------
    # ENTER
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

        # Create CAN only once
        if not hasattr(self.manager, "ams_can") or self.manager.ams_can is None:
            print("[CAN] Creating AMS_CAN instance")
            self.manager.ams_can = AMS_CAN()
            self.setup_can_and_lock_all()

        # 🔄 SYNC hardware → DB (SAFE)
        self.sync_hardware_to_db()

        # Load DB → UI
        self.reload_keys_from_db()
        self.populate_keys()

        # Unlock only allowed activity keys
        self.unlock_activity_keys()

        # Start polling CAN runtime events
        if self._can_poll_event is None:
            self._can_poll_event = Clock.schedule_interval(
                self.poll_can_events, 0.2
            )

    def on_leave(self, *args):
        if self._can_poll_event:
            self._can_poll_event.cancel()
            self._can_poll_event = None

    # =====================================================
    # CAN INIT / SECURITY
    # =====================================================
    def setup_can_and_lock_all(self):
        ams_can = self.manager.ams_can

        print("[CAN][INIT] Waiting for CAN boot…")
        sleep(6)

        print("[CAN][SECURITY] Locking ALL keys and LEDs OFF")
        for strip_id in ams_can.key_lists or [1, 2]:
            ams_can.lock_all_positions(strip_id)
            ams_can.set_all_LED_OFF(strip_id)

    # =====================================================
    # HARDWARE → DB SYNC (FIXED)
    # =====================================================
    def sync_hardware_to_db(self):
        ams_can = self.manager.ams_can

        print("\n[SYNC] 🔄 Syncing hardware state to DB")

        # Load DB keys first
        activity_id = self.activity_info.get("id")
        db_keys = get_keys_for_activity(activity_id)

        for key in db_keys:
            strip = key.get("strip")
            pos = key.get("position")

            if not strip or not pos:
                continue

            peg_id = ams_can.get_key_id(strip, pos)

            # ✅ KEY PRESENT → update using REAL peg_id
            if peg_id:
                print(f"[SYNC] 🟢 Key PRESENT strip={strip} pos={pos} peg_id={peg_id}")
                set_key_status_by_peg_id(peg_id, 0)

            # ❌ KEY NOT PRESENT → DO NOTHING (IMPORTANT)
            else:
                print(f"[SYNC] 🔴 Slot empty strip={strip} pos={pos} (no DB update)")

    # =====================================================
    # DATABASE
    # =====================================================
    def reload_keys_from_db(self):
        activity_id = self.activity_info.get("id")
        keys = get_keys_for_activity(activity_id)

        print(f"\n[DB][LOAD] Loaded {len(keys)} keys")

        self.keys_data = []
        for key in keys:
            status_text = "IN" if key["status"] == 0 else "OUT"
            print(
                f"[DB] id={key['id']} name={key['name']} "
                f"status={status_text} strip={key.get('strip')} pos={key.get('position')}"
            )

            self.keys_data.append({
                "key_id": str(key["id"]),
                "key_name": key["name"],
                "status": key["status"],
                "strip": key.get("strip"),
                "position": key.get("position"),
            })

    # =====================================================
    # UI RENDER
    # =====================================================
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

    # =====================================================
    # UNLOCK ONLY ACTIVITY KEYS
    # =====================================================
    def unlock_activity_keys(self):
        ams_can = self.manager.ams_can
        print(f"\n[CAN] 🔓 Unlocking {len(self.keys_data)} activity keys")

        for item in self.keys_data:
            if item["strip"] and item["position"]:
                ams_can.unlock_single_key(
                    int(item["strip"]),
                    int(item["position"])
                )

    # =====================================================
    # CAN RUNTIME EVENTS (AUTHORITATIVE)
    # =====================================================
    def poll_can_events(self, _dt):
        ams_can = self.manager.ams_can

        # 🔴 KEY TAKEN
        if ams_can.key_taken_event:
            peg_id = ams_can.key_taken_id
            print(f"\n[CAN] 🔴 KEY TAKEN peg_id={peg_id}")

            set_key_status_by_peg_id(peg_id, 1)
            self.reload_keys_from_db()
            self.populate_keys()

            ams_can.key_taken_event = False

        # 🟢 KEY INSERTED
        if ams_can.key_inserted_event:
            peg_id = ams_can.key_inserted_id
            print(f"\n[CAN] 🟢 KEY INSERTED peg_id={peg_id}")

            set_key_status_by_peg_id(peg_id, 0)
            self.reload_keys_from_db()
            self.populate_keys()

            ams_can.key_inserted_event = False

    # =====================================================
    # NAVIGATION
    # =====================================================
    def open_done_page(self, key_name, status, key_id):
        self.manager.selected_key_id = key_id
        self.manager.selected_key_name = key_name
        self.manager.current = "activity_done"
