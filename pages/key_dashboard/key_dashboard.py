# pages/key_dashboard/key_dashboard.py
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from components.base_screen import BaseScreen
from db import get_keys_for_activity
from test import AMS_CAN   # adjust module name to your actual file


class KeyItem(ButtonBehavior, BoxLayout):
    key_name = StringProperty("")
    status = StringProperty("")
    status_color = ListProperty([0, 1, 0, 1])
    dashboard = ObjectProperty(None)
    key_id = StringProperty("")

    def on_status(self, *_):
        # status: "IN"/"OUT" or 0/1
        if isinstance(self.status, int):
            self.status_color = [0, 1, 0, 1] if self.status == 0 else [1, 0, 0, 1]
        else:
            self.status_color = [0, 1, 0, 1] if self.status.upper() == "IN" else [1, 0, 0, 1]

    def on_release(self):
        if self.dashboard:
            self.dashboard.open_done_page(self.key_name, self.status, self.key_id)


class KeyDashboardScreen(BaseScreen):

    activity_code = StringProperty("")
    activity_name = StringProperty("")
    time_remaining = StringProperty("15")
    keys_data = ListProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.keys_data = []

    def on_enter(self, *args):
        """Called when entering key dashboard screen"""
        # Get activity and user info from manager
        self.activity_info = getattr(self.manager, 'activity_info', None)
        self.card_info = getattr(self.manager, 'card_info', None)

        if self.activity_info:
            self.activity_code = self.activity_info.get('code', '')
            self.activity_name = self.activity_info.get('name', '')
            self.time_remaining = str(self.activity_info.get('time_limit', 15))

            print(f"Activity: {self.activity_name} (Code: {self.activity_code})")

            # Load keys for this activity
            activity_id = self.activity_info.get('id')
            keys = get_keys_for_activity(activity_id)

            print(f"Found {len(keys)} keys for activity")

            # Convert to keys_data format (include strip & position)
            self.keys_data = []
            for key in keys:
                status_text = "IN" if key['status'] == 0 else "OUT"
                print(f"  - {key['name']} (ID: {key['id']}, Status: {status_text})")

                self.keys_data.append({
                    "key_id": str(key['id']),
                    "key_name": key['name'],
                    "status": key['status'],  # 0=IN, 1=OUT
                    "location": key.get('location', ''),
                    "description": key.get('description', ''),
                    "strip": key.get('strip'),
                    "position": key.get('position'),
                })
        else:
            print("⚠️ No activity info found!")
            self.activity_code = "N/A"
            self.activity_name = "No Activity"
            self.keys_data = []

        # Populate the UI
        self.populate_keys()

        # NEW: automatically unlock all displayed keys when screen is entered
        self.unlock_all_displayed_keys()

    def go_back(self):
        self.manager.transition.direction = "right"
        self.manager.current = "activity_code"

    def populate_keys(self):
        """Populate key grid with keys from database"""
        grid = self.ids.key_grid
        grid.clear_widgets()

        if not self.keys_data:
            print("No keys to display")
            return

        for item in self.keys_data:
            status_text = "IN" if item["status"] == 0 else "OUT"

            key_widget = KeyItem(
                key_id=item["key_id"],
                key_name=item["key_name"],
                status=status_text,
                dashboard=self,
            )
            grid.add_widget(key_widget)

    def unlock_all_displayed_keys(self):
        """Unlock all keys currently in keys_data using CAN."""
        if not self.keys_data:
            print("No keys to unlock.")
            return

        # Ensure there is a shared AMS_CAN instance on the manager
        if not hasattr(self.manager, "ams_can") or self.manager.ams_can is None:
            print("Creating AMS_CAN instance for key dashboard")
            self.manager.ams_can = AMS_CAN()

        ams_can = self.manager.ams_can

        keys_to_unlock = []
        for item in self.keys_data:
            strip = item.get("strip")
            pos = item.get("position")
            if strip is None or pos is None:
                print(f"Key {item.get('key_name')} missing strip/position, skipping")
                continue

            keys_to_unlock.append({
                "strip": int(strip),
                "position": int(pos),
                "name": item.get("key_name", "")
            })

        if not keys_to_unlock:
            print("No keys with valid strip/position to unlock.")
            return

        print(f"Unlocking {len(keys_to_unlock)} keys on enter...")
        results = ams_can.unlock_keys_batch(keys_to_unlock)

        for r in results:
            print(
                f"Strip {r['strip']} Pos {r['position']} "
                f"({r.get('name','')}): {'OK' if r['ok'] else 'FAILED'}"
            )

        # Optionally mark them as OUT in UI and refresh
        for item in self.keys_data:
            if item.get("strip") is not None and item.get("position") is not None:
                item["status"] = 1  # mark as OUT
        self.populate_keys()

    def open_done_page(self, key_name, status, key_id):
        """Navigate to activity done page with key info"""
        print(f"Key selected: {key_name} (ID: {key_id}, Status: {status})")

        # Store selected key info in manager
        self.manager.selected_key_id = key_id
        self.manager.selected_key_name = key_name

        done = self.manager.get_screen("activity_done")
        done.retrieved_text = f"{key_name} ({status})"
        done.returned_text = ""

        self.manager.transition.direction = "left"
        self.manager.current = "activity_done"
