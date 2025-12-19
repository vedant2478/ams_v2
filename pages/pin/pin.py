from kivy.properties import ListProperty, StringProperty, NumericProperty
from components.base_screen import BaseScreen
from db import verify_card_pin


class PinScreen(BaseScreen):
    pin = ListProperty([])
    pin_length = NumericProperty(0)
    message = StringProperty("")
    
    MAX_PIN = 5
    
    def on_enter(self):
        """Called when entering PIN screen"""
        self.pin.clear()
        self.pin_length = 0
        self.message = ""
        
        # Get card info from manager
        self.card_number = getattr(self.manager, 'card_number', None)
        self.card_info = getattr(self.manager, 'card_info', None)
        
        if self.card_info:
            print(f"PIN entry for: {self.card_info['name']} (Card: {self.card_number})")
        else:
            print("⚠️ No card info found!")
    
    def go_back(self):
        self.pin.clear()
        self.pin_length = 0
        self.manager.transition.direction = "right"
        self.manager.current = "card_scan"

    def on_keypad(self, value):
        if value.isdigit():
            if len(self.pin) < self.MAX_PIN:
                self.pin.append(value)
                self.pin_length = len(self.pin)
                print(f"PIN: {'*' * len(self.pin)}")

        elif value == "BACK":
            if self.pin:
                self.pin.pop()
                self.pin_length = len(self.pin)
                self.message = ""

        elif value == "ENTER":
            if len(self.pin) == self.MAX_PIN:
                self.validate_pin()
            else:
                self.message = f"Enter {self.MAX_PIN} digits"

    def validate_pin(self):
        """Validate PIN against database"""
        entered_pin = "".join(self.pin)
        
        # Check if card number exists
        if not self.card_number:
            print("✗ No card number found")
            self.message = "ERROR: No card"
            self.pin.clear()
            self.pin_length = 0
            return
        
        # Verify PIN with database
        is_valid = verify_card_pin(self.card_number, entered_pin)
        
        if is_valid:
            print(f"✓ PIN correct for card {self.card_number}")
            self.message = "PIN VERIFIED"
            
            # Navigate to Activity Code screen
            self.manager.transition.direction = "left"
            self.manager.current = "activity"
            
            # Clear PIN after navigation
            self.pin.clear()
            self.pin_length = 0
        else:
            print(f"✗ PIN incorrect for card {self.card_number}")
            self.message = "INCORRECT PIN"
            self.pin.clear()
            self.pin_length = 0
