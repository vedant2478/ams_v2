from kivy.properties import StringProperty, NumericProperty, ListProperty
from kivy.clock import Clock
from components.base_screen import BaseScreen

class ActivityDoneScreen(BaseScreen):
    retrieved_text = StringProperty("")
    returned_text = StringProperty("")
    timestamp_text = StringProperty("")
    countdown = NumericProperty(5)
    cards = ListProperty([])

    def on_pre_enter(self, *args):
        self.cards = [
            {
                "key_name": "Master Key 1",
                "taken_text": "2025-07-25 14:32:09",
                "returned_text": "2025-07-25 14:59:09",
            },
            {
                "key_name": "Master Key 1",
                "taken_text": "2025-07-25 14:32:09",
                "returned_text": "2025-07-25 14:59:09",
            },
            {
                "key_name": "Master Key 1",
                "taken_text": "2025-07-25 14:32:09",
                "returned_text": "2025-07-25 14:59:09",
            },
        ]
