# pages/key_dashboard/key_dashboard.py
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from components.base_screen import BaseScreen


class KeyItem(ButtonBehavior, BoxLayout):
    key_name = StringProperty("")
    status = StringProperty("")
    status_color = ListProperty([0, 1, 0, 1])
    dashboard = ObjectProperty(None)

    def on_status(self, *_):
        self.status_color = [0, 1, 0, 1] if self.status.upper() == "IN" else [1, 0, 0, 1]

    def on_release(self):
        if self.dashboard:
            self.dashboard.open_done_page(self.key_name, self.status)


class KeyDashboardScreen(BaseScreen):
    

    activity_code = StringProperty("A-452")
    time_remaining = StringProperty("12")   # ✅ this MUST exist
    keys_data = ListProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.keys_data = [
            {"key_name": "Master Key 1", "status": "IN"},
            {"key_name": "Locker Key 2", "status": "OUT"},
            {"key_name": "Container Key 1", "status": "IN"},
             {"key_name": "Master Key 1", "status": "IN"},
            {"key_name": "Locker Key 2", "status": "OUT"},
            {"key_name": "Container Key 1", "status": "IN"},
             {"key_name": "Master Key 1", "status": "IN"},
            {"key_name": "Locker Key 2", "status": "OUT"},
            {"key_name": "Container Key 1", "status": "IN"},
             {"key_name": "Master Key 1", "status": "IN"},
            {"key_name": "Locker Key 2", "status": "OUT"},
            {"key_name": "Container Key 1", "status": "IN"},
        ]

    def go_back(self):
        self.manager.current = "activity"


    def populate_keys(self):
        grid = self.ids.key_grid
        grid.clear_widgets()
        for item in self.keys_data:
            grid.add_widget(KeyItem(
                key_name=item["key_name"],
                status=item["status"],
                dashboard=self,
            ))

    def on_enter(self, *args):
        self.populate_keys()

    def open_done_page(self, key_name, status):
        done = self.manager.get_screen("activity_done")
        done.retrieved_text = f"{key_name} ({status})"
        done.returned_text = ""
        self.manager.current = "activity_done"
