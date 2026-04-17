# components/header/header.py
from datetime import datetime

from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty
from kivy.clock import Clock


class Header(BoxLayout):
    """
    Application header bar.

    - time_text  : auto-updated every second (HH:MM:SS)
    - site_text  : loaded from DB when first attached to a parent
    - status_text: set by each screen as needed (default SYSTEM READY)
    """

    site_text = StringProperty("SITE")
    status_text = StringProperty("SYSTEM READY")
    time_text = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Update time immediately, then every second
        self._clock_event = Clock.schedule_interval(self._update_time, 1)
        self._update_time(0)

    def on_parent(self, instance, parent):
        """Called when this header is added to a parent widget."""
        if parent is not None and self.site_text == "SITE":
            self._fetch_site_name()

    def _update_time(self, dt):
        self.time_text = datetime.now().strftime("%H:%M:%S")

    def _fetch_site_name(self):
        """Attempt to read site name from global App DB session."""
        try:
            from kivy.app import App
            app = App.get_running_app()
            if app and hasattr(app.root, 'db_session'):
                from db import get_site_name
                name = get_site_name(app.root.db_session)
                if name:
                    self.site_text = name
        except Exception:
            pass  # silently fail — site default is "SITE"
