import os
import sys
import ctypes
import threading
import subprocess
import _thread as thread
from datetime import datetime
from time import sleep

# custom imports
import amsbms
from amscan import *
from consts import *
from database import *
from model import *
# from ldap3 import Server, Connection

## Active Directory Configurations
# AD_SERVER = '192.168.1.98'
# AD_PORT = 389
# AD_KMS_USER_NAME='ITdemo@CSI.COM'
# AD_KMS_USER_PASSWORD = 'Csinc@2023'
# AD_Base_DN = 'DC=CSI,DC=COM'
#
#
# def checkUserRecordInAD(queryUserADName):
#     isBindSuccessful = False
#     s = Server(AD_SERVER, port=AD_PORT, get_info=all)
#     c = Connection(s, read_only=True, user=AD_KMS_USER_NAME, password=AD_KMS_USER_PASSWORD, check_names=True, auto_bind=True)
#     c.open()
#     isBindSuccessful = c.bind()
#     if isBindSuccessful:
#         c.search(AD_Base_DN, '(sAMAccountName='+ queryUserADName + ')',
#                  attributes=['displayName', 'userAccountControl', 'sAMAccountName', 'cn'])
#
#         userFound = [user.userAccountControl for user in c.entries if queryUserADName in user.sAMAccountName]
#         status = None
#         if len(userFound):
#             return userFound[0]     # return status code
#         else:
#             return 0                # 0 means user does not exists
#     else:
#         return -1                   # -1 signifies bind failed


def get_event_description(session, event_status):
    event_type = (
        session.query(AMS_Event_Types)
        .filter(AMS_Event_Types.eventId == event_status)
        .one_or_none()
    )
    return event_type.eventDescription


def play_emergency_music(BUZZ):
    i = 0
    while i < 4:
        BUZZ.write(1)
        sleep(0.5)
        BUZZ.write(0)
        sleep(0.5)
        i += 1


def show_error_msgs(lib_display, lib_Buzzer, msg1="ERROR OCCURED", msg2=None):
    #lib_Buzzer.setBuzzerOn()
    show_msg_on_display(lib_display, msg1=msg1, msg2=msg2, sleep_duration=2)
    #lib_Buzzer.setBuzzerOff()


def show_msg_on_display(lib_display, msg1=None, msg2=None, sleep_duration=0.5):
    lib_display.displayClear()
    if msg1:
        lib_display.displayString(msg1.encode("utf-8"), 1)
    if msg2:
        lib_display.displayString(msg2.encode("utf-8"), 2)
    if sleep_duration:
        sleep(sleep_duration)
        lib_display.displayClear()


def update_keys_status(ams_can, list_ID, session):
    for key_num in range(1, 15):
        key_id = ams_can.get_key_id(list_ID, key_num, delay=0.5)
        print(key_id)
        if key_id:
            current_key = (
                session.query(AMS_Keys).filter(AMS_Keys.peg_id == key_id).first()
            )
            if current_key:
                if (
                    current_key.current_pos_slot_no == current_key.keyPosition
                    and current_key.current_pos_strip_id == current_key.keyStrip
                ):
                    print(f"{current_key.keyName} present right slot")
                    current_key.keyStatus = SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT
                    current_key.color = "Green"
                # if (
                #     current_key.current_pos_slot_no == current_key.keyPosition
                #     and current_key.current_pos_strip_id == current_key.keyStrip
                # ):
                #     current_key.keyStatus = SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT
                #     current_key.color = 'Green'
                if (
                    current_key.current_pos_slot_no != current_key.keyPosition
                    or current_key.current_pos_strip_id != current_key.keyStrip
                ):
                    print(f"{current_key.keyName} present wrong slot")
                    current_key.keyStatus = SLOT_STATUS_KEY_PRESENT_WRONG_SLOT
                    current_key.color = "Black"
                session.commit()
            else:
                return
        else:
            session.query(AMS_Keys).filter(
                AMS_Keys.current_pos_strip_id == list_ID
            ).filter(AMS_Keys.current_pos_slot_no == (key_num)).update(
                {"keyStatus": SLOT_STATUS_KEY_NOT_PRESENT, "color": "White"}
            )
            session.commit()


def ams_header_line(session):
    ams_alarm_count = (
        session.query(AMS_Event_Log).filter(AMS_Event_Log.event_type != 3).count()
    )
    bcp = amsbms.batteryPc
    ams_header_line_str = "Alarm:" + str(ams_alarm_count) + " Bat:" + str(bcp) + "%"
    return ams_header_line_str


def initialize_hardware_peripherals():
    lib_display = ctypes.CDLL("libDisplay.so")
    lib_display.displayDefaultLoginMessage.argtypes = []
    lib_display.displayStringWithPosition.argtypes = [
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_int,
    ]
    lib_display.displayString.argtypes = [ctypes.c_char_p, ctypes.c_int]
    lib_display.displayClear.argtypes = []
    lib_display.displayInit.argtypes = []
    lib_display.displayClose.argtypes = []

    lib_display.displayInit()
    sleep(0.5)
    lib_display.displayClear()

    lib_Buzzer = ctypes.CDLL("libBuzzer.so")
    lib_Buzzer.setBuzzerOn.argtypes = []
    lib_Buzzer.setBuzzerOff.argtypes = []

    lib_keypad = ctypes.CDLL("libKeypad.so")
    lib_keypad.keypadInit.argtypes = []
    lib_keypad.keypadHandler.argtypes = [ctypes.c_int]
    lib_keypad.keypadClose.argtypes = [ctypes.c_int]
    FD_KEYPAD = lib_keypad.keypadInit()

    lib_KeyboxLock = ctypes.CDLL("libKeyboxLock.so")
    lib_KeyboxLock.getDoorSensorStatus1.argtypes = []
    lib_KeyboxLock.setKeyBoxLock.argtypes = [ctypes.c_int]
    lib_KeyboxLock.getDoorSensorStatus1.argtypes = []

    return lib_display, lib_Buzzer, lib_keypad, lib_KeyboxLock, FD_KEYPAD


def validate_(s):
    if s.count(".") != 3:
        return False
    ip_list = list(map(str, s.split(".")))
    for element in ip_list:
        if (
            int(element) < 0
            or int(element) > 255
            or (element[0] == "0" and len(element) != 1)
        ):
            return False
    return True


def get_ip_gw_subnet_input(lib_display, lib_keypad, FD_KEYPAD):
    new_ip_address = ""
    new_gw_address = ""
    new_subnet_address = ""

    show_msg_on_display(
        lib_display,
        msg1="Enter IP Address",
        sleep_duration=None,
    )

    while True:
        show_msg_on_display(
            lib_display,
            msg1="Enter IP Address",
            msg2=new_ip_address,
            sleep_duration=None,
        )
        key = lib_keypad.keypadHandler(FD_KEYPAD)
        key_str = str(KEY_DICT[str(key)])
        if key_str.isnumeric():
            new_ip_address += key_str
        elif key_str == ".":
            new_ip_address += "."
        elif key_str == "DN":
            new_ip_address = ""
        elif key_str == "UP":
            show_msg_on_display(lib_display, msg1="Cancelled!", msg2="Returning to Menu", sleep_duration=2)
            return None, None, None
        elif key_str == "ENTER":
            break

    show_msg_on_display(
        lib_display,
        msg1="Enter GW Address",
        sleep_duration=None,
    )

    while True:
        show_msg_on_display(
            lib_display,
            msg1="Enter GW Address",
            msg2=new_gw_address,
            sleep_duration=None,
        )
        key = lib_keypad.keypadHandler(FD_KEYPAD)
        key_str = str(KEY_DICT[str(key)])
        if key_str.isnumeric():
            new_gw_address += key_str
        elif key_str == ".":
            new_gw_address += "."
        elif key_str == "DN":
            new_gw_address = ""
        elif key_str == "UP":
            show_msg_on_display(lib_display, msg1="Cancelled!", msg2="Returning to Menu", sleep_duration=2)
            return None, None, None
        elif key_str == "ENTER":
            break

    show_msg_on_display(
        lib_display,
        msg1="Enter Subnet",
        sleep_duration=None,
    )

    while True:
        show_msg_on_display(
            lib_display,
            msg1="Enter Subnet Address",
            msg2=new_subnet_address,
            sleep_duration=None,
        )
        key = lib_keypad.keypadHandler(FD_KEYPAD)
        key_str = str(KEY_DICT[str(key)])
        if key_str.isnumeric():
            new_subnet_address += key_str
        elif key_str == ".":
            new_subnet_address += "."
        elif key_str == "DN":
            new_subnet_address = ""
        elif key_str == "UP":
            show_msg_on_display(lib_display, msg1="Cancelled!", msg2="Returning to Menu", sleep_duration=2)
            return None, None, None
        elif key_str == "ENTER":
            break

    if (
        validate_(new_gw_address)
        and validate_(new_ip_address)
        and validate_(new_subnet_address)
    ):
        return new_ip_address, new_gw_address, new_subnet_address
    return None, None, None


def change_ip_address_gateway(
    session, user_auth, ams_access_log, lib_display, lib_keypad, FD_KEYPAD
):
    show_msg_on_display(
        lib_display,
        msg1="Kindly Enter IP",
        msg2="GW & SubNet",
        sleep_duration=5,
    )
    new_ip_address, new_gw_address, new_subnet_address = get_ip_gw_subnet_input(
        lib_display, lib_keypad, FD_KEYPAD
    )

    if new_ip_address is None or new_gw_address is None or new_subnet_address is None:
        # User cancelled with Home (UP)
        show_msg_on_display(lib_display, msg1="Operation Cancelled", msg2="Returning", sleep_duration=2)
        return

    if new_ip_address and new_gw_address and new_subnet_address:
        print("process to change ip, subnet and gw begins.....")

        cabinet_info = session.query(AMS_Cabinet).one_or_none()
        cabinet_info.ipAddress = new_ip_address
        cabinet_info.gateway = new_gw_address
        cabinet_info.subnetMask = new_subnet_address
        session.commit()

        show_msg_on_display(
            lib_display,
            msg1="Rebooting",
            msg2="Cabinet",
            sleep_duration=2,
        )
        os.system(
            f"python3 /home/ams-core/ip_change.py {new_ip_address} {new_subnet_address} {new_gw_address}"
        )

    else:

        eventDesc = get_event_description(session, EVENT_IP_ADDRESS_CHANGE_FAILED)

        ams_event_log = AMS_Event_Log(
            userId=user_auth["id"],
            keyId=None,
            activityId=1,
            eventId=EVENT_IP_ADDRESS_CHANGE_FAILED,
            loginType="PIN",
            access_log_id=ams_access_log.id,
            timeStamp=datetime.now(TZ_INDIA),
            event_type=EVENT_TYPE_EVENT,
            is_posted=0,
        )
        session.add(ams_event_log)
        session.commit()


def get_key_interactions(
    ams_can,
    event_type,
    login_type,
    session,
    cabinet,
    ams_access_log,
    user_auth,
    lib_display,
    lib_Buzzer,
    keys_taken_list,
    keys_returned_list,
):

    key_record = None

    if ams_can.key_taken_event:
        print("############   Key has been taken out  ###########")
        for key in cabinet.keys:
            if key.peg_id == ams_can.key_taken_id:
                key_record = key
                break

        if key_record:
            keys_msg_print = (
                "Key taken: " + (key_record.keyName.ljust(4, " "))
            ).encode("utf-8")
            print(keys_msg_print)
            ams_access_log.keysTaken = str(key_record.id)
            session.commit()
            print("key taken peg id is : ", end="")
            print(ams_can.key_taken_id)
            session.query(AMS_Keys).filter(
                AMS_Keys.peg_id == ams_can.key_taken_id
            ).update(
                {
                    "keyTakenBy": user_auth["id"],
                    "keyTakenByUser": user_auth["name"],
                    "current_pos_strip_id": ams_can.key_taken_position_list,
                    "current_pos_slot_no": ams_can.key_taken_position_slot,
                    "keyTakenAtTime": datetime.now(TZ_INDIA),
                    "keyStatus": SLOT_STATUS_KEY_NOT_PRESENT,
                }
            )

            eventDesc = get_event_description(
                session,
                EVENT_KEY_TAKEN_CORRECT,
            )

            ams_event_log = AMS_Event_Log(
                userId=user_auth["id"],
                keyId=key_record.id,
                activityId=None,
                eventId=EVENT_KEY_TAKEN_CORRECT,
                loginType=login_type,
                access_log_id=ams_access_log.id,
                timeStamp=datetime.now(TZ_INDIA),
                event_type=EVENT_TYPE_EVENT,
                is_posted=0,
            )
            session.add(ams_event_log)
            session.commit()

            if key_record.keyName not in keys_taken_list:
                keys_taken_list.append(key_record.keyName)
        else:
            print("Key taken but key record not found for updating taken event")
            keys_msg_print = "Key not reg.    ".encode("utf-8")

        lib_display.displayClear()
        lib_display.displayString(keys_msg_print, 2)

        print("key taken out successfully....")
        ams_can.key_taken_event = False

    elif ams_can.key_inserted_event:
        print("############   key has been inserted  ###########")
        print("\n\nKEY INSERTED\n\n")
        for key in cabinet.keys:
            if key.peg_id == ams_can.key_inserted_id:
                key_record = key
                break

        if key_record:

            ams_can.set_single_LED_state(
                ams_can.key_inserted_position_list,
                ams_can.key_inserted_position_slot,
                CAN_LED_STATE_OFF,
            )
            keys_msg_print = (
                    "Key return:" + (key_record.keyName.ljust(4, " "))
            ).encode("utf-8")
            ams_access_log.keysReturned = str(key_record.id)
            session.commit()

            session.query(AMS_Keys).filter(
                AMS_Keys.peg_id == ams_can.key_inserted_id
            ).update(
                {
                    "current_pos_door_id": 1,
                    "keyTakenBy": None,
                    "keyTakenAtTime": None,
                    "current_pos_strip_id": ams_can.key_inserted_position_list,
                    "current_pos_slot_no": ams_can.key_inserted_position_slot,
                    "keyStatus": SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT,
                    "color": "Green",
                }
            )

            eventDesc = get_event_description(
                session,
                EVENT_KEY_RETURNED_RIGHT_SLOT,
            )

            ams_event_log = AMS_Event_Log(
                userId=user_auth["id"],
                keyId=key_record.id,
                activityId=None,
                eventId=EVENT_KEY_RETURNED_RIGHT_SLOT,
                loginType=login_type,
                access_log_id=ams_access_log.id,
                timeStamp=datetime.now(TZ_INDIA),
                event_type=EVENT_TYPE_EVENT,
                is_posted=0,
            )
            session.add(ams_event_log)
            session.commit()
            lib_display.displayClear()
            lib_display.displayString(keys_msg_print, 2)
            ams_can.key_inserted_event = False
            if key_record.keyName not in keys_returned_list:
                keys_returned_list.append(key_record.keyName)

            #####################################################################################
            # if (
            #     key_record.keyStrip == ams_can.key_inserted_position_list
            #     and key_record.keyPosition == ams_can.key_inserted_position_slot
            # ):
            #     ams_can.set_single_LED_state(
            #         ams_can.key_inserted_position_list,
            #         ams_can.key_inserted_position_slot,
            #         CAN_LED_STATE_OFF,
            #     )
            #     keys_msg_print = (
            #         "Key return:" + (key_record.keyName.ljust(4, " "))
            #     ).encode("utf-8")
            #     ams_access_log.keysReturned = str(key_record.id)
            #     session.commit()
            #
            #     session.query(AMS_Keys).filter(
            #         AMS_Keys.peg_id == ams_can.key_inserted_id
            #     ).update(
            #         {
            #             "current_pos_door_id": 1,
            #             "keyTakenBy": None,
            #             "keyTakenAtTime": None,
            #             "current_pos_strip_id": ams_can.key_inserted_position_list,
            #             "current_pos_slot_no": ams_can.key_inserted_position_slot,
            #             "keyStatus": SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT,
            #             "color": "Green",
            #         }
            #     )
            #
            #     eventDesc = get_event_description(
            #         session,
            #         EVENT_KEY_RETURNED_RIGHT_SLOT,
            #     )
            #
            #     ams_event_log = AMS_Event_Log(
            #         userId=user_auth["id"],
            #         keyId=key_record.id,
            #         activityId=None,
            #         eventId=EVENT_KEY_RETURNED_RIGHT_SLOT,
            #         loginType=login_type,
            #         access_log_id=ams_access_log.id,
            #         timeStamp=datetime.now(TZ_INDIA),
            #         event_type=event_type,
            #         eventDesc=eventDesc,
            #         is_posted=0,
            #     )
            #     session.add(ams_event_log)
            #     session.commit()
            #     lib_display.displayClear()
            #     lib_display.displayString(keys_msg_print, 2)
            #     ams_can.key_inserted_event = False
            #     if key_record.keyName not in keys_returned_list:
            #         keys_returned_list.append(key_record.keyName)
            #
            # elif (
            #     key_record.keyStrip != ams_can.key_inserted_position_list
            #     or key_record.keyPosition != ams_can.key_inserted_position_slot
            # ):
            #     ams_can.set_single_LED_state(
            #         ams_can.key_inserted_position_list,
            #         ams_can.key_inserted_position_slot,
            #         CAN_LED_STATE_BLINK,
            #     )
            #     keys_msg_print = (
            #         "Key return:" + (key_record.keyName.ljust(4, " "))
            #     ).encode("utf-8")
            #
            #     print("in wrong condition ", end="")
            #     print(keys_msg_print)
            #
            #     ams_access_log.keysReturned = str(key_record.id)
            #     session.commit()
            #
            #     session.query(AMS_Keys).filter(
            #         AMS_Keys.peg_id == ams_can.key_inserted_id
            #     ).update(
            #         {
            #             "current_pos_door_id": 1,
            #             "current_pos_strip_id": ams_can.key_inserted_position_list,
            #             "current_pos_slot_no": ams_can.key_inserted_position_slot,
            #             "keyStatus": SLOT_STATUS_KEY_PRESENT_WRONG_SLOT,
            #             "keyTakenAtTime": datetime.now(TZ_INDIA),
            #             "color": "Black",
            #         }
            #     )
            #
            #     eventDesc = get_event_description(
            #         session,
            #         EVENT_KEY_RETURNED_WRONG_SLOT,
            #     )
            #
            #     ams_event_log = AMS_Event_Log(
            #         userId=user_auth["id"],
            #         keyId=key_record.id,
            #         activityId=None,
            #         eventId=EVENT_KEY_RETURNED_WRONG_SLOT,
            #         loginType=login_type,
            #         access_log_id=ams_access_log.id,
            #         timeStamp=datetime.now(TZ_INDIA),
            #         event_type=event_type,
            #         eventDesc=eventDesc,
            #         is_posted=0,
            #     )
            #     session.add(ams_event_log)
            #     session.commit()
            #     lib_display.displayClear()
            #     lib_display.displayString(keys_msg_print, 2)
            #
            #     ams_can.key_inserted_event = False
            #     IS_KEY_IN_WRONG_SLOT = True
            #
            #     if not ams_can.get_key_id(key_record.keyStrip, key_record.keyPosition):
            #         ams_can.set_single_key_lock_state(
            #             ams_can.key_inserted_position_list,
            #             ams_can.key_inserted_position_slot,
            #             CAN_KEY_UNLOCKED,
            #         )
            #         ams_can.set_single_LED_state(
            #             ams_can.key_inserted_position_list,
            #             ams_can.key_inserted_position_slot,
            #             CAN_LED_STATE_BLINK,
            #         )
            #         ams_can.set_single_key_lock_state(
            #             key_record.keyStrip, key_record.keyPosition, CAN_KEY_UNLOCKED
            #         )
            #         ams_can.set_single_LED_state(
            #             key_record.keyStrip, key_record.keyPosition, CAN_LED_STATE_ON
            #         )
            #
            #         correct_key_POS = key_record.keyPosition + (
            #             (key_record.keyStrip - 1) * 14
            #         )
            #         current_key_POS = ams_can.key_inserted_position_slot + (
            #             (ams_can.key_inserted_position_list - 1) * 14
            #         )
            #         msg_line1 = ("Wrong slot  " + str(current_key_POS) + "  ").encode(
            #             "utf-8"
            #         )
            #         msg_line2 = ("Put in slot " + str(correct_key_POS) + "  ").encode(
            #             "utf-8"
            #         )
            #         lib_display.displayString(msg_line1, 1)
            #         lib_display.displayString(msg_line2, 2)
            #
            #         if key_record.id not in keys_returned_list:
            #             keys_returned_list.append(key_record.id)
            #         if key_record.id in keys_taken_list:
            #             keys_taken_list.remove(key_record.id)
            #     else:
            #         msg_line1 = "Keys are in ".encode("utf-8")
            #         msg_line2 = "Wrong Position".encode("utf-8")
            #         lib_display.displayClear()
            #         lib_display.displayString(msg_line1, 1)
            #         lib_display.displayString(msg_line2, 2)
            #
            #     IS_KEY_IN_WRONG_SLOT_Correct_Strip = key_record.keyStrip
            #     IS_KEY_IN_WRONG_SLOT_Correct_Pos = key_record.keyPosition
            #     IS_KEY_IN_WRONG_SLOT_Wrong_Strip = ams_can.key_inserted_position_slot
            #     IS_KEY_IN_WRONG_SLOT_Wrong_Pos = ams_can.key_inserted_position_list
            #     IS_KEY_IN_WRONG_SLOT_User_PIN = None
            #     #lib_Buzzer.setBuzzerOn()
            #     sleep(1)
            #     #lib_Buzzer.setBuzzerOff()
            #     if key_record.keyName not in keys_returned_list:
            #         keys_returned_list.append(key_record.keyName)

        else:
            print("Key inserted but key record not found for updating inserted event")
            msg_line1 = "Key record n/a  ".encode("utf-8")
            msg_line2 = "Register the key".encode("utf-8")
            lib_display.displayClear()
            lib_display.displayString(msg_line1, 1)
            lib_display.displayString(msg_line2, 2)
            sleep(1)
