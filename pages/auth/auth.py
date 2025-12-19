from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from datetime import datetime
from kivy.clock import Clock
from components.base_screen import BaseScreen

class AuthScreen(BaseScreen):

    def on_enter(self):
        # update time once per second (same pattern as Home)
        self.update_time()
        self._clock = Clock.schedule_interval(self.update_time, 1)

    def on_leave(self):
        if hasattr(self, "_clock"):
            self._clock.cancel()

    def update_time(self, *args):
        self.time_text = datetime.now().strftime("%H:%M")

    def go_back(self):
        self.manager.current = "home"

    def on_biometric(self):
        print("Biometric authentication selected")
    def on_card(self):
        self.manager.current = "card_scan"
