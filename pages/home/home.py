from kivy.properties import StringProperty
from kivy.clock import Clock
from datetime import datetime
from test2 import sync_hardware_to_db
from components.base_screen import BaseScreen
from db import get_site_name


class HomeScreen(BaseScreen):
    """
    Idle / Home Screen
    """

    time_text = StringProperty("--:--")
    status_text = StringProperty("SYSTEM READY")
    site_name = StringProperty("SITE")

    # --------------------------------------------------
    # SCREEN LIFECYCLE
    # --------------------------------------------------
    def on_enter(self):
        # Update time immediately + every second
        self.update_time()
        Clock.schedule_interval(self.update_time, 1)
        sync_hardware_to_db(self.manager.db_session)

        # 🔑 SAFE DB ACCESS (session already created by manager)
        session = self.manager.db_session
        self.site_name = get_site_name(session)

    def on_leave(self):
        Clock.unschedule(self.update_time)

    # --------------------------------------------------
    # UI HELPERS
    # --------------------------------------------------
    def update_time(self, *args):
        self.time_text = datetime.now().strftime("%H:%M")

    def open_config(self):
        # Navigate to PIN screen (admin check happens there)
        self.manager.transition.direction = "left"
        self.manager.current = "admin_home"

    def on_start_pressed(self):
        self.manager.current = "auth"
