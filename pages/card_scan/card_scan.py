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
        self._event = None

    def go_back(self, *args):
        """Return to previous (auth) screen and stop card reading."""
        self.stop_card_reading()
        self.manager.transition.direction = "right"
        self.manager.current = "auth"

    def on_enter(self):
        self.progress = 0
        self.instruction_text = "Show your card"
        Clock.schedule_interval(self.update_time, 1)

        # Normal procedure: init AMSBMS and start scan
        try:
            self.bms = AMSBMS(port="/dev/ttyAML1", baud=9600)
        except Exception as e:
            print(f"Error opening /dev/ttyAML1: {e}")
            self.instruction_text = "Reader error"
            self.bms = None
            self.card_reading = False
            return

        # Start card reading in background
        self.card_reading = True
        Thread(target=self.poll_card, daemon=True).start()

        # Animate progress bar (60s total, tick every 0.5s)
        self._event = Clock.schedule_interval(self.update_progress, 0.5)

    def on_leave(self):
        self.stop_card_reading()
        if self._event is not None:
            self._event.cancel()
            self._event = None
        Clock.unschedule(self.update_time)

    def stop_card_reading(self):
        """Stop card reading and cleanup the BMS/bus."""
        self.card_reading = False
        if self.bms:
            try:
                self.bms.stop()
            except Exception as e:
                print(f"Error stopping BMS: {e}")
            self.bms = None

    def update_time(self, dt):
        """Update time display."""
        self.time_text = datetime.now().strftime("%I:%M %p")

    def poll_card(self):
        """Background thread to continuously poll for cards."""
        timeout = 60  # 60 seconds timeout
        start_time = time.time()

        while self.card_reading and (time.time() - start_time) < timeout:
            try:
                if not self.bms:
                    break
                card_no = self.bms.get_cardNo()
                if card_no:
                    Clock.schedule_once(
                        lambda dt, c=card_no: self.handle_card_result(c), 0
                    )
                    return
                time.sleep(0.2)
            except Exception as e:
                print(f"Error polling card: {e}")
                break

        # Timeout - no card detected
        Clock.schedule_once(lambda dt: self.handle_card_result(None), 0)

    def handle_card_result(self, card_no):
        """Handle card read result (runs on main thread)."""
        self.card_reading = False

        if self._event is not None:
            self._event.cancel()
            self._event = None

        if card_no is not None and str(card_no).strip():
            print(f"✓ Card {card_no} detected")

            card_info = check_card_exists(card_no)
            print(card_info)

            if card_info["exists"]:
                print(f"✓ Card found: {card_info['name']}")
                self.instruction_text = f"Welcome {card_info['name']}"
                self.manager.card_number = str(card_no)
                self.manager.card_info = card_info
                self.progress = 100
                Clock.schedule_once(self.go_to_pin, 0.5)
            else:
                print(f"✗ Card {card_no} not found in database")
                self.instruction_text = "INVALID CARD!"
                self.progress = 0
        else:
            print("No card detected within timeout, returning to previous screen")
            self.instruction_text = "No card detected"
            self.progress = 0
            self.go_back()

    def update_progress(self, dt):
        """Animate progress while waiting (60s total)."""
        if self.progress >= 95:
            return
        self.progress += 100.0 / 120.0

    def go_to_pin(self, dt):
        self.stop_card_reading()
        self.manager.current = "pin"
