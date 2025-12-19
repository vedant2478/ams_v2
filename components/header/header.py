from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty

from db import get_site_name   # global helper

class Header(BoxLayout):
    site_text = StringProperty("")
    status_text = StringProperty("")
    time_text = StringProperty("")

    def on_kv_post(self, base_widget):
        self.site_text = get_site_name()
