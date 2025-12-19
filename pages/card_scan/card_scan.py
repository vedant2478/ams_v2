# pages/card_scan/card_scan.py
from kivy.uix.screenmanager import Screen
from kivy.properties import NumericProperty, StringProperty
from kivy.clock import Clock
from threading import Thread
from datetime import datetime
from components.base_screen import BaseScreen
from card_reader_helper import read_card_from_hardware

class CardScanScreen(BaseScreen):
    progress = NumericProperty(0)
    instruction_text = StringProperty("Show your card")
    time_text = StringProperty("")  # <-- ADD THIS LINE

    def go_back(self):
        self.manager.transition.direction = "right"
        self.manager.current = "auth"
    
    def on_enter(self):
        self.progress = 0
        self.instruction_text = "Show your card"
        
        # Update time display
        Clock.schedule_interval(self.update_time, 1)
        
        # Start card reading in background
        Thread(target=self.poll_card, daemon=True).start()
        
        # Animate progress bar
        self._event = Clock.schedule_interval(self.update_progress, 0.5)

    def on_leave(self):
        if hasattr(self, "_event"):
            self._event.cancel()
        Clock.unschedule(self.update_time)
    
    def update_time(self, dt):
        """Update time display"""
        self.time_text = datetime.now().strftime("%I:%M %p")

    def poll_card(self):
        """Poll hardware for card (15 seconds timeout)"""
        card_no = read_card_from_hardware(timeout_seconds=15)
        Clock.schedule_once(lambda dt: self.handle_card_result(card_no), 0)
    
    def handle_card_result(self, card_no):
        """Handle card read result"""
        if card_no > 0:
            # Card detected
            print(f"✓ Card {card_no} detected")
            self.instruction_text = f"Card detected: {card_no}"
            self.manager.card_number = card_no
            self.progress = 100
            
            if hasattr(self, "_event"):
                self._event.cancel()
            
            Clock.schedule_once(self.go_to_pin, 0.5)
        else:
            # Timeout - no card detected
            print("✗ Card read timeout")
            self.instruction_text = "TIMEOUT!!!"
            self.progress = 0
            
            if hasattr(self, "_event"):
                self._event.cancel()
            
            # Show error for 2 seconds, then go back
            Clock.schedule_once(lambda dt: self.go_back(), 2)

    def update_progress(self, dt):
        """Animate progress while waiting"""
        if self.progress >= 95:
            return
        self.progress += 100 / 30  # 15 seconds total

    def go_to_pin(self, dt):
        self.manager.transition.direction = "left"
        self.manager.current = "pin"
