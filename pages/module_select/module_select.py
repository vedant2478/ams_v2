from datetime import datetime
from kivy.clock import Clock
from components.base_screen import BaseScreen


class ModuleSelectScreen(BaseScreen):

    def on_enter(self):
        self.update_time()
        self._clock = Clock.schedule_interval(self.update_time, 1)

    def on_leave(self):
        if hasattr(self, "_clock"):
            self._clock.cancel()

    def update_time(self, *args):
        self.time_text = datetime.now().strftime("%H:%M")

    def go_back(self):
        self.manager.current = "home"

    def on_attendance(self):
        print("Attendance selected")


    def on_kms(self):
        print("kms  selected")
        self.manager.current = "auth"


