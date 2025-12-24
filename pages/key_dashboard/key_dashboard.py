# pages/key_dashboard/key_dashboard.py
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from components.base_screen import BaseScreen
from db import get_keys_for_activity, toggle_key_status_and_get_position



class KeyItem(ButtonBehavior, BoxLayout):
    key_name = StringProperty("")
    status = StringProperty("")        # "IN" or "OUT" for display
    status_color = ListProperty([0, 1, 0, 1])
    dashboard = ObjectProperty(None)
    key_id = StringProperty("")

    def on_status(self, *_):
        if isinstance(self.status, int):
            self.status_color = [0, 1, 0, 1] if self.status == 0 else [1, 0, 0, 1]
        else:
            self.status_color = [0, 1, 0, 1] if self.status.upper() == "IN" else [1, 0, 0, 1]

    def on_release(self):
        if self.dashboard:
            self.dashboard.toggle_key_and_open_done(self)


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

            print(keys)
            
            print(f"Found {len(keys)} keys for activity")
            
            # Convert to keys_data format
            self.keys_data = []
            for key in keys:
                status_text = "IN" if key['status'] == 0 else "OUT"
                print(f"  - {key['name']} (ID: {key['id']}, Status: {status_text})")
                
                self.keys_data.append({
                    "key_id": str(key['id']),
                    "key_name": key['name'],
                    "status": key['status'],  # 0=IN, 1=OUT
                    "location": key.get('location', ''),
                    "description": key.get('description', '')
                })
        else:
            print("⚠️ No activity info found!")
            self.activity_code = "N/A"
            self.activity_name = "No Activity"
            self.keys_data = []
        
        # Populate the UI
        self.populate_keys()

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
            # Convert status to text for display
            status_text = "IN" if item["status"] == 0 else "OUT"
            
            key_widget = KeyItem(
                key_id=item["key_id"],
                key_name=item["key_name"],
                status=status_text,
                dashboard=self,
            )
            grid.add_widget(key_widget)

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

    def toggle_key_and_open_done(self, key_widget: KeyItem):
        key_id = key_widget.key_id
        print(f"Toggling key ID: {key_id}")

        key_info = toggle_key_status_and_get_position(key_id)
        if not key_info:
            print("Key not found in DB")
            return

        # Update status text on widget
        new_status = key_info["status"]  # 0=IN, 1=OUT
        status_text = "IN" if new_status == 0 else "OUT"
        key_widget.status = status_text  # triggers on_status -> status_color

        # Position & strip from DB
        strip = key_info["strip"]
        position = key_info["position"]
        print(f"Key {key_id} now {status_text}, strip={strip}, position={position}")

        # Save for use in next screen / CAN logic
        self.manager.selected_key_id = key_id
        self.manager.selected_key_name = key_info["name"]
        self.manager.selected_key_strip = strip
        self.manager.selected_key_position = position
        self.manager.selected_key_status = new_status

        # Go to done page if you still want that flow
        done = self.manager.get_screen("activity_done")
        done.retrieved_text = f"{key_info['name']} ({status_text})"
        done.returned_text = ""
        self.manager.transition.direction = "left"
        self.manager.current = "activity_done"
