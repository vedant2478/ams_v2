from kivy.properties import StringProperty, NumericProperty
from kivy.clock import Clock
from components.base_screen import BaseScreen


class ActivityDoneScreen(BaseScreen):

    retrieved_text = StringProperty("Master Key 1 (IN)")
    returned_text = StringProperty("Master Key 1 (OUT)")
    timestamp_text = StringProperty("2025-07-25 14:32:09 UTC")

    countdown = NumericProperty(5)

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
