from kivy.properties import ListProperty, StringProperty, NumericProperty
from components.base_screen import BaseScreen
from db import verify_activity_code

from datetime import datetime
from csi_ams.model import AMS_Event_Log
from csi_ams.utils.commons import (
    TZ_INDIA,
    EVENT_ACTIVITY_CODE_CORRECT,
    EVENT_TYPE_EVENT,
    get_event_description,
)


class ActivityCodeScreen(BaseScreen):
    code = ListProperty([])
    code_length = NumericProperty(0)
    message = StringProperty("")

    MAX_CODE = 2   # only 2 digits

    def on_enter(self):
        """Called when entering activity code screen"""
        self.code.clear()
        self.code_length = 0
        self.message = ""

        # Get user info from manager
        self.card_info = getattr(self.manager, "card_info", None)

        if self.card_info:
            print(
                f"Activity code entry for user: "
                f"{self.card_info['name']} (ID: {self.card_info['id']})"
            )
        else:
            print("⚠️ No user info found!")

    def go_back(self):
        self.code.clear()
        self.code_length = 0
        self.manager.transition.direction = "right"
        self.manager.current = "pin"

    def on_keypad(self, value):
        if value.isdigit():
            if len(self.code) < self.MAX_CODE:
                self.code.append(value)
                self.code_length = len(self.code)
                print(f"Code: {'*' * len(self.code)}")

        elif value == "BACK":
            if self.code:
                self.code.pop()
                self.code_length = len(self.code)
                self.message = ""

        elif value == "ENTER":
            if len(self.code) == self.MAX_CODE:
                self.validate_code()
            else:
                self.message = f"Enter {self.MAX_CODE} digits"

    def validate_code(self):
        """Validate activity code against database and log events"""
        entered_code = "".join(self.code)

        # Check if user info exists
        if not self.card_info or not self.card_info.get("id"):
            print("✗ No user ID found")
            self.message = "ERROR: No user"
            self.code.clear()
            self.code_length = 0
            return

        user_id = self.card_info["id"]

        # Verify activity code with database
        result = verify_activity_code(user_id, entered_code)

        if result["valid"]:
            print(f"✓ Activity code correct: {result['name']}")
            self.message = f"{result['name']}"

            session = self.manager.db_session
            ams_access_log = self.manager.ams_access_log
            final_signin_mode = self.manager.final_auth_mode

            try:
                # --------------------------------------------------
                # 1️⃣ UPDATE GLOBAL ACCESS LOG
                # --------------------------------------------------
                if ams_access_log:
                    ams_access_log.activityCodeEntryTime = datetime.now(TZ_INDIA)
                    ams_access_log.activityCode = int(entered_code)
                    ams_access_log.event_type_id = EVENT_TYPE_EVENT
                    session.commit()

                # --------------------------------------------------
                # 2️⃣ CREATE EVENT LOG (ACTIVITY CODE CORRECT)
                # --------------------------------------------------
                eventDesc = get_event_description(
                    session, EVENT_ACTIVITY_CODE_CORRECT
                )

                ams_event_log = AMS_Event_Log(
                    userId=user_id,
                    keyId=None,
                    activityId=int(entered_code),
                    eventId=EVENT_ACTIVITY_CODE_CORRECT,
                    loginType=final_signin_mode,
                    access_log_id=ams_access_log.id if ams_access_log else None,
                    timeStamp=datetime.now(TZ_INDIA),
                    event_type=EVENT_TYPE_EVENT,
                    eventDesc=eventDesc,
                    is_posted=0,
                )
                print(ams_event_log)

                session.add(ams_event_log)
                session.commit()

            except Exception as e:
                session.rollback()
                print(f"[DB ERROR] Activity code logging failed: {e}")

            # --------------------------------------------------
            # 3️⃣ CONTINUE NORMAL FLOW
            # --------------------------------------------------
            self.manager.activity_info = result
            self.manager.transition.direction = "left"
            self.manager.current = "key_dashboard"

            self.code.clear()
            self.code_length = 0

        else:
            print(
                f"✗ Activity code invalid: "
                f"{result.get('message', 'Unknown error')}"
            )
            self.message = result.get("message", "Incorrect Code")
            self.code.clear()
            self.code_length = 0
