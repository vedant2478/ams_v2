from kivy.properties import ListProperty, StringProperty, NumericProperty
from components.base_screen import BaseScreen


class PinScreen(BaseScreen):
    pin = ListProperty([])
    pin_length = NumericProperty(0)

    message = StringProperty("")
    

    MAX_PIN = 5

    def go_back(self):
        self.manager.current = "home"

    def on_keypad(self, value):
        if value.isdigit():
            if len(self.pin) < self.MAX_PIN:
                self.pin.append(value)
                self.pin_length = len(self.pin)

        elif value == "BACK":
            if self.pin:
                self.pin.pop()
                self.pin_length = len(self.pin)

        elif value == "ENTER":
            self.validate_pin()

    def validate_pin(self):
        entered_pin = "".join(self.pin)

        if entered_pin == "12345":
            self.message = "PIN VERIFIED"

            # 👉 Navigate to Activity Code screen
            self.manager.transition.direction = "left"
            self.manager.current = "activity"

            # Optional: clear PIN after navigation
            self.pin.clear()
            self.pin_length = 0

        else:
            self.message = "Incorrect PIN"
            self.pin.clear()
            self.pin_length = 0
