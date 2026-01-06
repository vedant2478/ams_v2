from kivy.uix.screenmanager import Screen


class AdminScreen(Screen):
    """
    Admin Configuration Screen
    Accessible only after Admin PIN validation
    """

    def open_peg_registration(self):
        """
        Navigate to Peg Registration flow
        """
        print("[ADMIN] Peg Registration selected")

        # Change screen name if you already have a peg screen
        self.manager.transition.direction = "left"
        self.manager.current = "peg_registration"

    def open_card_registration(self):
        """
        Navigate to Card Registration flow
        """
        print("[ADMIN] Card Registration selected")

        # Change screen name if you already have a card screen
        self.manager.transition.direction = "left"
        self.manager.current = "card_registration"

    def go_home(self):
        """
        Return to Home Screen
        """
        self.manager.transition.direction = "right"
        self.manager.current = "home"
