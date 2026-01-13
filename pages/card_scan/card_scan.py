# pages/card_scan/card_scan.py
from kivy.uix.screenmanager import Screen
from kivy.properties import NumericProperty, StringProperty
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
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
        self.manager.card_registration_mode = False

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

    def show_card_exists_popup(self):
        """Show popup when card already exists during registration mode."""
        layout = BoxLayout(orientation="vertical", padding=10, spacing=10)

        lbl = Label(text="Card already exists!")
        btn = Button(text="Back", size_hint=(1, 0.3))

        layout.add_widget(lbl)
        layout.add_widget(btn)

        popup = Popup(
            title="Error",
            content=layout,
            size_hint=(0.6, 0.4),
            auto_dismiss=False,
        )

        def _back(instance):
            popup.dismiss()
            self.go_back()

        btn.bind(on_release=_back)
        popup.open()

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
            # Card found in DB
            if self.manager.card_registration_mode:
                # Registration mode but card already exists -> show popup
                print(f"✗ Card {card_no} already exists, cannot register")
                self.instruction_text = "Card already exists!"
                
                # Stop scanning and timeout
                self.card_reading = False
                if self._timeout_event is not None:
                    self._timeout_event.cancel()
                    self._timeout_event = None

                self.show_card_exists_popup()
            else:
                # Normal mode: valid card found -> go to PIN
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
            # Card NOT in DB
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
                self.instruction_text = "INVALID CARD!"
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
