from datetime import datetime
from kivy.clock import Clock
from components.base_screen import BaseScreen
from model import AUTH_MODE_CARD , AUTH_MODE_PIN

class AuthScreen(BaseScreen):

    def on_enter(self):
        self.update_time()
        self._clock = Clock.schedule_interval(self.update_time, 1)

        # reset global auth values
        self.manager.auth_mode = None
        self.manager.final_auth_mode = None

    def on_leave(self):
        if hasattr(self, "_clock"):
            self._clock.cancel()

    def update_time(self, *args):
        self.time_text = datetime.now().strftime("%H:%M")

    def go_back(self):
        self.manager.current = "home"

    def on_biometric(self):
        print("Biometric authentication selected")

        self.manager.auth_mode = 3
        self.manager.final_auth_mode = "BIOMETRIC"

        # self.manager.current = "biometric"

    def on_card(self):
        print("Card authentication selected")

        self.manager.auth_mode = AUTH_MODE_CARD
        self.manager.final_auth_mode = "CARD"

        self.manager.current = "card_scan"

    def on_pin(self):
        print("PIN authentication selected")

        self.manager.auth_mode = AUTH_MODE_PIN
        self.manager.final_auth_mode = "PIN"

        self.manager.current = "pin"
