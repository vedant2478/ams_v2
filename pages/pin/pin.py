from kivy.properties import ListProperty, StringProperty, NumericProperty
from components.base_screen import BaseScreen
from db import verify_card_pin

from datetime import datetime
from csi_ams.model import AMS_Access_Log, AMS_Event_Log
from csi_ams.utils.commons import (
    TZ_INDIA,
    get_event_description,
)
from csi_ams.model import *


class PinScreen(BaseScreen):
    pin = ListProperty([])
    pin_length = NumericProperty(0)
    message = StringProperty("")

    MAX_PIN = 5

    def on_enter(self):
        """Called when entering PIN screen"""
        self.pin.clear()
        self.pin_length = 0
        self.message = ""

        # Get card info from ScreenManager
        self.card_number = getattr(self.manager, "card_number", None)
        self.card_info = getattr(self.manager, "card_info", None)

        if self.card_info:
            print(
                f"PIN entry for: {self.card_info['name']} (Card: {self.card_number})"
            )
        else:
            print("⚠️ No card info found!")

    def go_back(self):
        self.pin.clear()
        self.pin_length = 0
        self.manager.transition.direction = "right"
        self.manager.current = "card_scan"

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
                self.validate_pin()
            else:
                self.message = f"Enter {self.MAX_PIN} digits"

def validate_pin(self):
    """Validate PIN and commit LOGIN logs"""
    entered_pin = "".join(self.pin)

    # --------------------------------------------------
    # SAFETY CHECK
    # --------------------------------------------------
    if not self.card_number:
        self.message = "ERROR: No card"
        self.pin.clear()
        self.pin_length = 0
        return

    session = self.manager.db_session  # ✅ DEFINE SESSION EARLY

    # --------------------------------------------------
    # VERIFY PIN
    # --------------------------------------------------
    is_valid = verify_card_pin(self.card_number, entered_pin)

    if not is_valid:
        self.message = "INCORRECT PIN"
        self.pin.clear()
        self.pin_length = 0

        ams_access_log = AMS_Access_Log(
            signInTime=datetime.now(TZ_INDIA),
            signInMode=self.manager.auth_mode,
            signInFailed=1,
            signInSucceed=0,
            signInUserId=None,
            activityCodeEntryTime=None,
            activityCode=None,
            doorOpenTime=None,
            keysAllowed=None,
            keysTaken=None,
            keysReturned=None,
            doorCloseTime=None,
            event_type_id=EVENT_LOGIN_FAILED,
            is_posted=0,
        )
        session.add(ams_access_log)
        session.commit()

        eventDesc = get_event_description(session, EVENT_LOGIN_FAILED)

        ams_event_log = AMS_Event_Log(
            userId=0,
            keyId=None,
            activityId=None,
            eventId=EVENT_LOGIN_FAILED,
            loginType=self.manager.final_auth_mode,
            access_log_id=ams_access_log.id,
            timeStamp=datetime.now(TZ_INDIA),
            event_type=EVENT_TYPE_ALARM,
            eventDesc=eventDesc,
            is_posted=0,
        )
        session.add(ams_event_log)
        session.commit()
        return

    # --------------------------------------------------
    # PIN SUCCESS
    # --------------------------------------------------
    print(f"✓ PIN correct for card {self.card_number}")
    self.message = "PIN VERIFIED"

    ams_user = AMS_Users()
    user_auth = ams_user.get_user_id(
        session,
        self.manager.auth_mode,
        card_no=self.card_number
    )

    # --------------------------------------------------
    # 🔒 VALIDATE AUTH OBJECT
    # --------------------------------------------------
    if (
        not isinstance(user_auth, dict)
        or user_auth.get("ResultCode") != AUTH_RESULT_SUCCESS
        or "id" not in user_auth
    ):
        print("❌ Invalid user_auth:", user_auth)
        self.message = "AUTH ERROR"
        return

    user_id = user_auth["id"]  # ✅ SAFE NOW

    # --------------------------------------------------
    # CREATE ACCESS LOG
    # --------------------------------------------------
    ams_access_log = AMS_Access_Log(
        signInTime=datetime.now(TZ_INDIA),
        signInMode=self.manager.auth_mode,
        signInFailed=0,
        signInSucceed=1,
        signInUserId=user_id,
        activityCodeEntryTime=None,
        activityCode=None,
        doorOpenTime=None,
        keysAllowed=None,
        keysTaken=None,
        keysReturned=None,
        doorCloseTime=None,
        event_type_id=EVENT_LOGIN_SUCCEES,
        is_posted=0,
    )

    session.add(ams_access_log)
    session.commit()

    self.manager.ams_access_log = ams_access_log
    self.manager.access_log_id = ams_access_log.id

    # --------------------------------------------------
    # CREATE EVENT LOG
    # --------------------------------------------------
    eventDesc = get_event_description(session, EVENT_LOGIN_SUCCEES)

    ams_event_log = AMS_Event_Log(
        userId=user_id,  # ✅ FIXED
        keyId=None,
        activityId=None,
        eventId=EVENT_LOGIN_SUCCEES,
        loginType=self.manager.final_auth_mode,
        access_log_id=ams_access_log.id,
        timeStamp=datetime.now(TZ_INDIA),
        event_type=EVENT_TYPE_EVENT,
        eventDesc=eventDesc,
        is_posted=0,
    )

    session.add(ams_event_log)
    session.commit()

    # --------------------------------------------------
    # MOVE TO NEXT SCREEN
    # --------------------------------------------------
    self.pin.clear()
    self.pin_length = 0
    self.manager.transition.direction = "left"
    self.manager.current = "activity"
