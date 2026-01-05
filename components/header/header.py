from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty


class Header(BoxLayout):
    site_text = StringProperty("SITE")
    status_text = StringProperty("")
    time_text = StringProperty("")
