from kivy.properties import ListProperty, StringProperty, NumericProperty
from components.base_screen import BaseScreen
from db import verify_activity_code


class ActivityCodeScreen(BaseScreen):
    code = ListProperty([])
    code_length = NumericProperty(0)
    message = StringProperty("")
    
    MAX_CODE = 2   # only 2 digits

    def on_enter(self):
        """Called when entering activity code screen"""
        self.code.clear()
        self.code_length = 0
        self.message = ""
        
        # Get user info from manager
        self.card_info = getattr(self.manager, 'card_info', None)
        
        if self.card_info:
            print(f"Activity code entry for user: {self.card_info['name']} (ID: {self.card_info['id']})")
        else:
            print("⚠️ No user info found!")

    def go_back(self):
        self.code.clear()
        self.code_length = 0
        self.manager.transition.direction = "right"
        self.manager.current = "pin"

    def on_keypad(self, value):
        if value.isdigit():
            if len(self.code) < self.MAX_CODE:
                self.code.append(value)
                self.code_length = len(self.code)
                print(f"Code: {'*' * len(self.code)}")

        elif value == "BACK":
            if self.code:
                self.code.pop()
                self.code_length = len(self.code)
                self.message = ""

        elif value == "ENTER":
            if len(self.code) == self.MAX_CODE:
                self.validate_code()
            else:
                self.message = f"Enter {self.MAX_CODE} digits"

    def validate_code(self):
        """Validate activity code against database"""
        entered_code = "".join(self.code)
        
        # Check if user info exists
        if not self.card_info or not self.card_info.get('id'):
            print("✗ No user ID found")
            self.message = "ERROR: No user"
            self.code.clear()
            self.code_length = 0
            return
        
        user_id = self.card_info['id']
        
        # Verify activity code with database
        result = verify_activity_code(user_id, entered_code)
        
        if result["valid"]:
            print(f"✓ Activity code correct: {result['name']}")
            self.message = f"{result['name']}"
            
            # Store activity info in manager
            self.manager.activity_info = result
            
            # Navigate to Key Dashboard
            self.manager.transition.direction = "left"
            self.manager.current = "key_dashboard"
            
            # Clear code after navigation
            self.code.clear()
            self.code_length = 0
        else:
            print(f"✗ Activity code invalid: {result.get('message', 'Unknown error')}")
            self.message = result.get('message', 'Incorrect Code')
            self.code.clear()
            self.code_length = 0
