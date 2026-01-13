from kivy.properties import ListProperty, StringProperty, NumericProperty
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button

from components.base_screen import BaseScreen

from datetime import datetime

from db import verify_card_pin, log_access_and_event, verify_or_assign_card_pin
from csi_ams.utils.commons import TZ_INDIA
from csi_ams.model import *
from model import ADMIN_PIN


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
    # POPUPS
    # --------------------------------------------------
    def show_confirm_update_popup(self, on_yes, on_no=None):
        layout = BoxLayout(orientation="vertical", padding=10, spacing=10)

        lbl = Label(text="Card already assigned.\nUpdate card?")
        btns = BoxLayout(size_hint=(1, 0.3), spacing=10)

        yes_btn = Button(text="Yes")
        no_btn = Button(text="No")

        btns.add_widget(yes_btn)
        btns.add_widget(no_btn)

        layout.add_widget(lbl)
        layout.add_widget(btns)

        popup = Popup(
            title="Confirm",
            content=layout,
            size_hint=(0.7, 0.4),
            auto_dismiss=False,
        )

        def _yes(instance):
            popup.dismiss()
            on_yes()

        def _no(instance):
            popup.dismiss()
            if on_no:
                on_no()

        yes_btn.bind(on_release=_yes)
        no_btn.bind(on_release=_no)

        popup.open()

    def show_done_popup(self, message="Card registered"):
        layout = BoxLayout(orientation="vertical", padding=10, spacing=10)

        lbl = Label(text=message)
        btn = Button(text="Done", size_hint=(1, 0.3))

        layout.add_widget(lbl)
        layout.add_widget(btn)

        popup = Popup(
            title="Success",
            content=layout,
            size_hint=(0.6, 0.4),
            auto_dismiss=False,
        )

        def _close(instance):
            popup.dismiss()
            self.manager.card_registration_mode = False

        btn.bind(on_release=_close)
        popup.open()

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
                    print(f"→ verify_or_assign_card_pin returned: {ok}, {reason}")

                    # no PIN in DB
                    if not ok and reason == "no_pin":
                        self.message = "Incorrect PIN"
                        print("✗ No user found with this PIN")
                        return

                    # PIN exists but belongs to some other card
                    if not ok and reason == "conflict":
                        print("⚠️ PIN already has another card assigned")

                        def on_yes_update():
                            ok2, reason2 = verify_or_assign_card_pin(
                                session=session,
                                card_number=self.card_number,
                                pin=entered_pin,
                                force_update=True,
                            )
                            print(f"→ force_update returned: {ok2}, {reason2}")
                            if ok2 and reason2 in ("ok_updated", "ok_existing"):
                                print(f"✓ Card updated to {self.card_number}")
                                self.message = "Card updated"
                                self.show_done_popup("Card updated")
                            else:
                                self.message = "Update failed"

                        def on_no_update():
                            print("↩ Card not updated")
                            self.message = "Card not updated"

                        self.show_confirm_update_popup(
                            on_yes=on_yes_update,
                            on_no=on_no_update,
                        )
                        self.manager.card_registration_mode = False
                        return

                    # success cases from function
                    if ok and reason == "ok_assigned":
                        print(f"✓ Card {self.card_number} assigned to this PIN")
                        self.message = "User added"
                        self.show_done_popup("User added")
                    elif ok and reason in ("ok_existing", "ok_updated"):
                        # ok_existing: same card; ok_updated: changed to this card
                        print(f"✓ PIN has card {self.card_number}")
                        self.message = "PIN VERIFIED"
                        self.show_done_popup("PIN VERIFIED")

                    self.manager.card_registration_mode = False
                    return

                else:
                    self.validate_pin()
            else:
                self.message = f"Enter {self.MAX_PIN} digits"

    # --------------------------------------------------
    # PIN VALIDATION (EXISTING FLOW)
    # --------------------------------------------------
    def validate_pin(self):
        entered_pin = "".join(self.pin)
        session = self.manager.db_session

        # ---------------- SAFETY ----------------
        if entered_pin == ADMIN_PIN:
            self.manager.current = "admin_home"
            return

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

        self.manager.access_log_id = result["access_log_id"]

        self.reset_pin()
        self.manager.transition.direction = "left"
        self.manager.current = "activity"

    # --------------------------------------------------
    # HELPERS
    # --------------------------------------------------
    def reset_pin(self):
        self.pin.clear()
        self.pin_length = 0
