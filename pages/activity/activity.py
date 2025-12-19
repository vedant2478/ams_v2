from kivy.properties import ListProperty, StringProperty, NumericProperty
from components.base_screen import BaseScreen


class ActivityCodeScreen(BaseScreen):
    code = ListProperty([])
    code_length = NumericProperty(0)

    message = StringProperty("")
    

    MAX_CODE = 2   # only 2 digits

    def go_back(self):
        self.manager.current = "home"

    def on_keypad(self, value):
        if value.isdigit():
            if len(self.code) < self.MAX_CODE:
                self.code.append(value)
                self.code_length = len(self.code)

        elif value == "BACK":
            if self.code:
                self.code.pop()
                self.code_length = len(self.code)

        elif value == "ENTER":
            self.validate_code()

    def validate_code(self):
        entered = "".join(self.code)

        # 2‑digit activity code
        if entered == "54":
            self.message = "CODE VERIFIED"
            self.code.clear()
            self.code_length = 0
            # go to key_dashboard screen
            if self.manager:
                self.manager.current = "key_dashboard"
        else:
            self.message = "Incorrect Code"
            self.code.clear()
            self.code_length = 0
