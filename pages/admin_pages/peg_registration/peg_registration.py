# peg_scan_screen.py

from datetime import datetime
from threading import Thread

from kivy.properties import StringProperty, NumericProperty
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout

from components.base_screen import BaseScreen
from peg_registration import register_pegs
from amscan import AMS_CAN


class PegScanCompletePopup(Popup):
    """Popup shown when peg registration completes"""
    message_text = StringProperty("")


class PegScanScreen(BaseScreen):
    """
    Screen for peg registration with visual feedback
    States: idle -> scanning -> complete/error
    """
    
    time_text = StringProperty("")
    status_text = StringProperty("Initializing...")
    instruction_text = StringProperty("Please wait...")
    progress = NumericProperty(0)
    scan_state = StringProperty("idle")  # idle, scanning, complete, error
    scan_in_progress = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ams_can = None
        self._clock_event = None
    
    def on_enter(self, *args):
        """Called when screen is entered"""
        # Update clock
        self._clock_event = Clock.schedule_interval(self.update_clock, 1)
        self.update_clock(0)
        
        # Start registration in background
        Clock.schedule_once(lambda dt: self.start_registration(), 0.5)
    
    def on_leave(self, *args):
        """Called when leaving screen"""
        if self._clock_event:
            self._clock_event.cancel()
    
    def update_clock(self, dt):
        """Update time display"""
        self.time_text = datetime.now().strftime("%I:%M %p")
    
    def start_registration(self):
        """Start peg registration in background thread"""
        self.scan_in_progress = True
        self.scan_state = "scanning"
        self.status_text = "Initializing..."
        self.instruction_text = "Setting up hardware connection..."
        self.progress = 0
        
        # Run in thread to avoid blocking UI
        thread = Thread(target=self._run_registration)
        thread.daemon = True
        thread.start()
    
    def _run_registration(self):
        """Background thread for registration"""
        try:
            # Step 1: Initialize CAN
            Clock.schedule_once(
                lambda dt: self._update_status("Initializing CAN bus...", 10)
            )
            
            self.ams_can = AMS_CAN()
            self.ams_can.get_version_number(1)
            self.ams_can.get_version_number(2)
            
            from time import sleep
            sleep(2)
            
            Clock.schedule_once(
                lambda dt: self._update_status("CAN bus ready", 20)
            )
            
            # Step 2: Sync hardware
            Clock.schedule_once(
                lambda dt: self._update_status("Syncing hardware state...", 30)
            )
            sleep(1)
            
            # Step 3: Call registration function
            Clock.schedule_once(
                lambda dt: self._update_status("Checking keys...", 40)
            )
            
            result = register_pegs(
                session=self.manager.db_session,
                ams_can=self.ams_can,
                user_id=self.manager.user_id
            )
            
            # Update progress during scan
            Clock.schedule_once(
                lambda dt: self._update_status("Scanning pegs...", 60)
            )
            sleep(1)
            
            Clock.schedule_once(
                lambda dt: self._update_status("Writing to database...", 80)
            )
            sleep(1)
            
            # Handle result
            if result['success']:
                Clock.schedule_once(
                    lambda dt: self._on_success(result)
                )
            else:
                Clock.schedule_once(
                    lambda dt: self._on_error(result['message'])
                )
            
        except Exception as e:
            import traceback
            error_msg = f"Error: {str(e)}"
            print(traceback.format_exc())
            Clock.schedule_once(
                lambda dt: self._on_error(error_msg)
            )
        
        finally:
            # Cleanup
            if self.ams_can:
                self.ams_can.cleanup()
                self.ams_can = None
            
            self.scan_in_progress = False
    
    def _update_status(self, message, progress_value):
        """Update UI status from background thread"""
        self.status_text = message
        self.progress = progress_value
    
    def _on_success(self, result):
        """Handle successful registration"""
        self.scan_state = "complete"
        self.status_text = "Registration Complete!"
        self.instruction_text = f"{result.get('pegs_registered', 0)} pegs registered successfully"
        self.progress = 100
        
        # Show popup
        popup = PegScanCompletePopup(
            message_text=f"Successfully registered {result.get('pegs_registered', 0)} pegs"
        )
        popup.bind(on_dismiss=lambda x: self.go_home())
        popup.open()
    
    def _on_error(self, error_message):
        """Handle registration error"""
        self.scan_state = "error"
        self.status_text = "Registration Failed"
        self.instruction_text = error_message
        self.progress = 0
    
    def cancel_scan(self):
        """Cancel ongoing scan"""
        if not self.scan_in_progress:
            self.go_back()
    
    def go_home(self):
        """Return to home screen"""
        self.manager.current = "home"
    
    def go_back(self):
        """Go back to previous screen"""
        self.manager.current = "admin"  # or wherever you came from
