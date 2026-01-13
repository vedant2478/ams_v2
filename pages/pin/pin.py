from kivy.properties import ListProperty, StringProperty, NumericProperty
from components.base_screen import BaseScreen

from datetime import datetime

from db import verify_card_pin, log_access_and_event, verify_or_assign_card_pin
from csi_ams.utils.commons import TZ_INDIA
from csi_ams.model import *
from model import ADMIN_PIN
from user_registration_service import UserRegistrationService


class PinScreen(BaseScreen):
    pin = ListProperty([])
    pin_length = NumericProperty(0)
    message = StringProperty("")

    MAX_PIN = 5

    # --------------------------------------------------
    # SCREEN ENTER
    # --------------------------------------------------
    def on_enter(self):
        self.pin.clear()
        self.pin_length = 0
        self.message = ""

        self.card_number = getattr(self.manager, "card_number", None)
        self.card_info = getattr(self.manager, "card_info", None)

        if self.card_info:
            print(
                f"PIN entry for: {self.card_info['name']} "
                f"(Card: {self.card_number})"
            )
        else:
            print("⚠️ No card info found!")

    # --------------------------------------------------
    # NAVIGATION
    # --------------------------------------------------
    def go_back(self):
        self.reset_pin()
        self.manager.transition.direction = "right"
        self.manager.current = "card_scan"

    # --------------------------------------------------
    # KEYPAD HANDLER
    # --------------------------------------------------
    def on_keypad(self, value):
        if value.isdigit():
            if len(self.pin) < self.MAX_PIN:
                self.pin.append(value)
                self.pin_length = len(self.pin)

        elif value == "BACK":
            if self.pin:
                self.pin.pop()
                self.pin_length = len(self.pin)
                self.message = ""

        elif value == "ENTER":
                if len(self.pin) == self.MAX_PIN:
                    if self.manager.card_registration_mode:
                        print("→ Card registration mode active", self.card_number)

                        session = self.manager.db_session
                        entered_pin = "".join(self.pin)

                        ok, reason = verify_or_assign_card_pin(
                            session=session,
                            card_number=self.card_number,
                            pin=entered_pin,
                        )

                        # no PIN in DB
                        if not ok and reason == "no_pin":
                            self.message = "Incorrect PIN"
                            print("✗ No user found with this PIN")
                            return

                        # PIN exists but belongs to some other card
                        if not ok and reason == "conflict":
                            print("⚠️ PIN already has another card assigned")
                            # replace this with a Kivy popup if needed
                            answer = input("Card already assigned. Update card? (y/N): ").strip().lower()
                            if answer == "y":
                                # call again but now force update in the function (see below)
                                ok2, reason2 = verify_or_assign_card_pin(
                                    session=session,
                                    card_number=self.card_number,
                                    pin=entered_pin,
                                    force_update=True,   # add this optional arg to your function
                                )
                                if ok2:
                                    print(f"✓ Card updated to {self.card_number}")
                                    self.message = "Card updated"
                                else:
                                    self.message = "Update failed"
                            else:
                                print("↩ Card not updated")
                                self.message = "Card not updated"
                            return

                        # success cases from function
                        if ok and reason == "ok_assigned":
                            print(f"✓ Card {self.card_number} assigned to this PIN")
                            self.message = "User added"
                        elif ok and reason == "ok_existing":
                            print(f"✓ PIN already had this card")
                            self.message = "PIN VERIFIED"

                        self.manager.card_registration_mode = False
                        return

                    else:
                        self.validate_pin()
                else:
                    self.message = f"Enter {self.MAX_PIN} digits"

    # --------------------------------------------------
    # PIN VALIDATION
    # --------------------------------------------------
    def validate_pin(self):
        entered_pin = "".join(self.pin)
        session = self.manager.db_session

        # ---------------- SAFETY ----------------
        if entered_pin == ADMIN_PIN:
                self.manager.current = "admin_home"
        if not self.card_number:
            self.message = "ERROR: No card"
            self.reset_pin()
            return

        # ---------------- VERIFY PIN ----------------
        is_valid = verify_card_pin(
            session=session,
            card_number=self.card_number,
            pin=entered_pin,
        )


        # ❌ PIN FAILED
        if not is_valid:
            self.message = "INCORRECT PIN"
            self.reset_pin()


            log_access_and_event(
                session=session,
                event_id=EVENT_LOGIN_FAILED,
                event_type=EVENT_TYPE_ALARM,
                auth_mode=self.manager.auth_mode,
                login_type=self.manager.final_auth_mode,
                user_id=None,
                access_log_updates={
                    "signInFailed": 1,
                    "signInSucceed": 0,
                },
            )
            return

        # ✅ PIN SUCCESS
        self.message = "PIN VERIFIED"
        print(f"✓ PIN correct for card {self.card_number}")

        user_id = self.card_info["id"]
        print(f"✓ User ID: {user_id}")

        result = log_access_and_event(
            session=session,
            event_id=EVENT_LOGIN_SUCCEES,
            event_type=EVENT_TYPE_EVENT,
            auth_mode=self.manager.auth_mode,
            login_type=self.manager.final_auth_mode,
            user_id=user_id,
            access_log_updates={
                "signInFailed": 0,
                "signInSucceed": 1,
            },
        )

        # Save access log for next screens
        self.manager.access_log_id = result["access_log_id"]

        # ---------------- MOVE TO ACTIVITY ----------------
        self.reset_pin()
        self.manager.transition.direction = "left"
        self.manager.current = "activity"

    # --------------------------------------------------
    # HELPERS
    # --------------------------------------------------
    def reset_pin(self):
        self.pin.clear()
        self.pin_length = 0
