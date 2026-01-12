from kivy.uix.screenmanager import Screen
from peg_registration import PegRegistrationService


class AdminScreen(Screen):
    """
    Admin Configuration Screen
    Peg registration is triggered directly from here
    """

    def open_peg_registration(self):
        print("[ADMIN] Peg Registration clicked")

        if hasattr(self.manager, "peg_reg_service"):
            if self.manager.peg_reg_service._active:
                print("[ADMIN] Peg registration already running")
                return

        self.manager.peg_reg_service = PegRegistrationService(self.manager)
        self.manager.peg_reg_service.start()

    def open_card_registration(self):
        print("[ADMIN] Card Registration selected")
        self.manager.card_registration_mode = True
        self.manager.current = "card_scan"

    def go_home(self):
        print("[ADMIN] Go Home")
        self.manager.current = "home"
