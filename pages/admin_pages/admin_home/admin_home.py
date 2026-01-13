# admin_screen.py

from kivy.uix.screenmanager import Screen


class AdminScreen(Screen):
    """
    Admin Configuration Screen
    """

    def open_peg_registration(self):
        """Navigate to peg scan screen"""
        print("[ADMIN] Peg Registration clicked")
        
        # Navigate to peg scan screen
        self.manager.current = "peg_scan"

    def open_card_registration(self):
        """Navigate to card registration"""
        print("[ADMIN] Card Registration selected")
        self.manager.card_registration_mode = True
        self.manager.current = "card_scan"

    def go_home(self):
        """Return to home screen"""
        print("[ADMIN] Go Home")
        self.manager.current = "home"
        self.manager.card_registration_mode = False
