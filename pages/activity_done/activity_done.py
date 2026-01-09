from kivy.properties import StringProperty, NumericProperty, ListProperty
from kivy.clock import Clock

from components.base_screen import BaseScreen


class ActivityDoneScreen(BaseScreen):
    """
    Screen shown after the activity is completed.
    It supports a list of key records, each with:
        - key_name
        - taken
        - returned
    The KV file should iterate over `key_items` and create one card per item.
    """

    # Old single‑line labels (keep if you still use them anywhere in the KV)
    retrieved_text = StringProperty("Master Key 1 (IN)")
    returned_text = StringProperty("Master Key 1 (OUT)")
    timestamp_text = StringProperty("2025-07-25 14:32:09 UTC")

    # New: list of key records used to populate the cards
    # Example item: {"key_name": "Master Key 1", "taken": "...", "returned": "..."}
    key_items = ListProperty([])

    countdown = NumericProperty(5)

    def on_pre_enter(self, *args):
        """
        Populate the list before the screen is shown.
        Replace this with your real data source.
        """
        # Example data – plug in your own list here
        self.key_items = [
            {
                "key_name": "Master Key 1",
                "taken": "2025-07-25 14:32:09",
                "returned": "2025-07-25 14:59:09",
            },
            {
                "key_name": "Master Key 2",
                "taken": "2025-07-25 13:10:00",
                "returned": "2025-07-25 13:45:30",
            },
            {
                "key_name": "Master Key 3",
                "taken": "2025-07-25 12:00:00",
                "returned": "2025-07-25 12:30:00",
            },
        ]

    def on_enter(self, *args):
        self.countdown = 5
        self._event = Clock.schedule_interval(self._tick, 1)

    def on_leave(self, *args):
        if hasattr(self, "_event"):
            self._event.cancel()

    def _tick(self, dt):
        if self.countdown > 0:
            self.countdown -= 1
        if self.countdown == 0 and self.manager:
            self.manager.current = "home"

    def on_return_pressed(self):
        if hasattr(self, "_event"):
            self._event.cancel()
        if self.manager:
            self.manager.current = "home"
