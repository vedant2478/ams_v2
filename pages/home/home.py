from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.clock import Clock
from datetime import datetime
from components.base_screen import BaseScreen
from db import get_site_name

class HomeScreen(BaseScreen):
    """
    Idle / Home Screen
    """

    time_text = StringProperty("--:--")
    status_text = StringProperty("SYSTEM READY")
    site_name = get_site_name()

    def on_enter(self):
        self.update_time()
        Clock.schedule_interval(self.update_time, 1)

    def on_leave(self):
        Clock.unschedule(self.update_time)

    def update_time(self, *args):
        self.time_text = datetime.now().strftime("%H:%M")

    def on_start_pressed(self):
        self.manager.current = "auth"

