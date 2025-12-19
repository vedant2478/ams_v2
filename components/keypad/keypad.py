from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ObjectProperty


class Keypad(BoxLayout):
    """
    Reusable numeric keypad.
    Sends pressed key value to parent via callback.
    """
    callback = ObjectProperty(None)

    def key_pressed(self, value):
        if self.callback:
            self.callback(value)
