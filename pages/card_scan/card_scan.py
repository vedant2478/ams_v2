# pages/card_scan/card_scan.py
from kivy.uix.screenmanager import Screen
from kivy.properties import NumericProperty, StringProperty
from kivy.clock import Clock
from threading import Thread
from db import check_card_exists
from datetime import datetime
import time
from components.base_screen import BaseScreen
from amsbms import AMSBMS


class CardScanScreen(BaseScreen):
    progress = NumericProperty(0)
    instruction_text = StringProperty("Show your card")
    time_text = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bms = None
        self.card_reading = False

    def go_back(self):
        self.stop_card_reading()
        self.manager.transition.direction = "right"
        self.manager.current = "auth"
    
    def on_enter(self):
        self.progress = 0
        self.instruction_text = "Show your card"
        
        # Update time display
        Clock.schedule_interval(self.update_time, 1)
        
        # Initialize BMS
        self.bms = AMSBMS(port="/dev/ttyAML1", baud=9600)
        
        # Start card reading in background
        self.card_reading = True
        Thread(target=self.poll_card, daemon=True).start()
        
        # Animate progress bar
        self._event = Clock.schedule_interval(self.update_progress, 0.5)

    def on_leave(self):
        self.stop_card_reading()
        if hasattr(self, "_event"):
            self._event.cancel()
        Clock.unschedule(self.update_time)
    
    def stop_card_reading(self):
        """Stop card reading and cleanup"""
        self.card_reading = False
        if self.bms:
            self.bms.stop()
            self.bms = None
    
    def update_time(self, dt):
        """Update time display"""
        self.time_text = datetime.now().strftime("%I:%M %p")

    def poll_card(self):
        """Background thread to continuously poll for cards"""
        timeout = 15  # 15 seconds timeout
        start_time = time.time()
        
        while self.card_reading and (time.time() - start_time) < timeout:
            try:
                # Get card number from BMS
                card_no = self.bms.get_cardNo()
                
                if card_no:
                    # Card detected! Schedule UI update on main thread
                    Clock.schedule_once(lambda dt: self.handle_card_result(card_no), 0)
                    return
                
                time.sleep(0.2)  # Poll every 200ms
                
            except Exception as e:
                print(f"Error polling card: {e}")
                time.sleep(0.5)
        
        # Timeout - no card detected
        Clock.schedule_once(lambda dt: self.handle_card_result(None), 0)
    
    def handle_card_result(self, card_no):
        """Handle card read result (runs on main thread)"""
        if card_no is not None and str(card_no).strip():
            print(f"✓ Card {card_no} detected")
            
            # Check if card exists in database
            card_info = check_card_exists(card_no)
            
            if card_info["exists"]:
                print(f"✓ Card found: {card_info['name']}")
                self.instruction_text = f"Welcome {card_info['name']}"
                self.manager.card_number = str(card_no)
                self.manager.card_info = card_info  # Store full card info
                self.progress = 100
                
                if hasattr(self, "_event"):
                    self._event.cancel()
                
                Clock.schedule_once(self.go_to_pin, 0.5)
            else:
                print(f"✗ Card {card_no} not found in database")
                self.instruction_text = "INVALID CARD!"
                self.progress = 0

    def update_progress(self, dt):
        """Animate progress while waiting"""
        if self.progress >= 95:
            return
        self.progress += 100 / 30  # 15 seconds total

    def go_to_pin(self, dt):
        self.stop_card_reading()
        self.manager.transition.direction = "left"
        self.manager.current = "pin"
