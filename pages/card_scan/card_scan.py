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
        self._timeout_event = None

    def go_back(self, *args):
        """Return to home screen and stop card reading."""
        self.stop_card_reading()
        self.manager.transition.direction = "right"
        self.manager.current = "home"

    def on_enter(self):
        self.progress = 0
        self.instruction_text = "Show your card"
        Clock.schedule_interval(self.update_time, 1)

        # Init AMSBMS
        try:
            self.bms = AMSBMS(port="/dev/ttyAML1", baud=9600)
        except Exception as e:
            print(f"Error opening /dev/ttyAML1: {e}")
            self.instruction_text = "Reader error"
            self.bms = None
            self.card_reading = False
            self.manager.current = "home"
            return

        # Start card reading in background
        self.card_reading = True
        Thread(target=self.poll_card, daemon=True).start()

        # Animate progress bar (30s total, tick every 0.5s)
        self._event = Clock.schedule_interval(self.update_progress, 0.5)

        # Schedule timeout to go back after 30 seconds
        self._timeout_event = Clock.schedule_once(self.on_timeout, 30)

    def on_leave(self):
        self.stop_card_reading()
        if self._event is not None:
            self._event.cancel()
            self._event = None
        if self._timeout_event is not None:
            self._timeout_event.cancel()
            self._timeout_event = None
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

    def on_timeout(self, dt):
        """Called after 30 seconds if no valid card detected."""
        print("⏱ Card scan timeout (30s), returning to home")
        self.instruction_text = "No card detected"
        self.progress = 0
        self.go_back()

    def poll_card(self):
        """Background thread to continuously poll for cards until valid or timeout."""
        while self.card_reading:
            try:
                if not self.bms:
                    break
                card_no = self.bms.get_cardNo()
                if card_no:
                    Clock.schedule_once(
                        lambda dt, c=card_no: self.handle_card_result(c), 0
                    )
                    # Do NOT return here; we keep scanning until valid card
                time.sleep(0.2)
            except Exception as e:
                print(f"Error polling card: {e}")
                break

    def handle_card_result(self, card_no):
        """Handle card read result (runs on main thread)."""
        if not card_no or not str(card_no).strip():
            return

        print(f"✓ Card {card_no} detected")

        card_info = check_card_exists(
            session=self.manager.db_session,
            card_number=card_no
        )

        if card_info["exists"]:
            # Valid card found -> stop scanning and go to PIN
            print(f"✓ Card found: {card_info['name']}")
            self.instruction_text = f"Welcome {card_info['name']}"
            self.manager.card_number = str(card_no)
            self.manager.card_info = card_info
            self.progress = 100

            # Cancel timeout and stop reading
            self.card_reading = False
            if self._timeout_event is not None:
                self._timeout_event.cancel()
                self._timeout_event = None

            Clock.schedule_once(self.go_to_pin, 0.5)
        else:
            # Invalid card -> just show message, keep scanning
            print(f"✗ Card {card_no} not found in database")

            if self.manager.card_registration_mode:
                # NEW CARD in registration mode -> go to PIN
                print("→ Card registration mode active, going to PIN screen")
                self.instruction_text = "NEW CARD!"
                self.manager.new_card = True
                self.manager.card_number = str(card_no)
                self.progress = 100

                # Stop scanning and timeout
                self.card_reading = False
                if self._timeout_event is not None:
                    self._timeout_event.cancel()
                    self._timeout_event = None

                Clock.schedule_once(self.go_to_pin, 1.0)
            else:
                # Normal mode: invalid card, keep scanning
                self.instruction_text = "INVALID CARD! Scan again"
                # Do NOT stop card_reading, do NOT cancel timeout

    def update_progress(self, dt):
        """Animate progress while waiting (30s total)."""
        if self.progress >= 95:
            return
        # 30 seconds = 60 ticks at 0.5s each
        # so increment by 100/60 per tick
        self.progress += 100.0 / 60.0

    def go_to_pin(self, dt):
        self.stop_card_reading()
        self.manager.current = "pin"
