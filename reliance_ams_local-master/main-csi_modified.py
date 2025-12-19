import os
import sys
import pytz
import ctypes
import threading
import subprocess
from amscan import *
from doublyLinkedList import InstanceDoublyLinkedList
from model import *
from time import sleep
import _thread as thread
from ctypes import c_ulonglong
from datetime import date, datettime
from sqlalchemy import Column, Integer, String, ForeignKey, Table, create_engine
from sqlalchemy.orm import relationship, backref, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.expression import distinct, false, intersect_all, null, true
from sqlalchemy.sql.functions import concat, func, now, user
from sqlalchemy.sql.sqltypes import DATETIME, INTEGER, SMALLINT, DateTime, Time
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Table,
    create_engine,
    or_,
    and_,
    BINARY,
    func,
)


AUTH_MODE_PIN = 1
AUTH_MODE_CARD_PIN = 2
AUTH_MODE_BIO = 3

AUTH_RESULT_SUCCESS = 0
AUTH_RESULT_FAILED = 1

ACTIVITY_ALLOWED = 0
ACTIVITY_ERROR_USER_INVALID = 1
ACTIVITY_ERROR_TIME_INVALID = 2
ACTIVITY_ERROR_WEEKDAY_INVALID = 3
ACTIVITY_ERROR_FREQUENCY_EXCEEDED = 4
ACTIVITY_ERROR_CODE_INCORRECT = 5

EVENT_TYPE_EVENT = 1
EVENT_TYPE_ALARM = 2

EVENT_LOGIN_SUCCEES = 1
EVENT_LOGIN_FAILED = 2
EVENT_ACTIVITY_CODE_CORRECT = 3
EVENT_ACTIVITY_CODE_WRONG = 4
EVENT_ACTIVITY_CODE_NOT_ALLOWED = 5
EVENT_DOOR_OPEN = 6
EVENT_DOOR_CLOSED = 7
EVENT_DOOR_OPENED_TOO_LONG = 8
EVENT_KEY_TAKEN_CORRECT = 9
EVENT_KEY_TAKEN_WRONG = 10
EVENT_KEY_RETURNED_RIGHT_SLOT = 11
EVENT_KEY_RETURNED_WRONG_SLOT = 12
EVENT_ACTIVITY_CODE_TIMEOUT = 13
EVENT_EMERGENCY_DOOR_OPEN = 14

MAIN_DOOR_LOCK = 0
MAIN_DOOR_UN_LOCK = 1

SLOT_STATUS_KEY_NOT_PRESENT = 0
SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT = 1
SLOT_STATUS_KEY_PRESENT_WRONG_SLOT = 2


BATTERY_CHARGE_PC = 0
tz_IN = pytz.timezone("Asia/Kolkata")


KEY_DICT = {
    "2": 1,
    "5": 2,
    "8": 3,
    "3": 4,
    "6": 5,
    "9": 6,
    "4": 7,
    "7": 8,
    "10": 9,
    "108": 0,
    "103": "F1",
    "479": "F2",
    "28": ".",
    "465": "UP",
    "11": "DN",
    "55": "ENTER",
}


def get_key_interactions(
    ams_can2,
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
    lib_display.displayInit()
    if ams_can2.key_taken_event:
        print("############   Key has been taken out  ###########")
        for key in cabinet.keys:
            if key.peg_id == ams_can2.key_taken_id:
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
            session.query(AMS_Keys).filter(
                AMS_Keys.peg_id == ams_can2.key_taken_id
            ).update(
                {
                    "keyTakenBy": user_auth["id"],
                    "keyTakenByUser": user_auth["name"],
                    "current_pos_strip_id": ams_can2.key_taken_position_list,
                    "current_pos_slot_no": ams_can2.key_taken_position_slot,
                    "keyTakenAtTime": datetime.now(tz_IN),
                    "keyStatus": SLOT_STATUS_KEY_NOT_PRESENT,
                }
            )
            session.commit()

            ams_event_log = AMS_Event_Log(
                userId=user_auth["id"],
                keyId=key_record.id,
                activityId=None,
                eventId=EVENT_KEY_TAKEN_CORRECT,
                loginType="PIN",
                access_log_id=ams_access_log.id,
                timeStamp=datetime.now(tz_IN),
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

        show_msg_on_display(
            lib_display, msg1=None, msg2=keys_msg_print, sleep_duration=None
        )

        print("key taken out successfully....")
        ams_can2.key_taken_event = False

    elif ams_can2.key_inserted_event:
        print("############   key has been inserted  ###########")
        print("\n\nKEY INSERTED\n\n")
        for key in cabinet.keys:
            if key.peg_id == ams_can2.key_inserted_id:
                key_record = key

        if key_record:
            if (
                key_record.keyStrip == ams_can2.key_inserted_position_list
                and key_record.keyPosition == ams_can2.key_inserted_position_slot
            ):
                ams_can2.set_single_LED_state(
                    ams_can2.key_inserted_position_list,
                    ams_can2.key_inserted_position_slot,
                    CAN_LED_STATE_OFF,
                )
                keys_msg_print = (
                    "Key return:" + (key_record.keyName.ljust(4, " "))
                ).encode("utf-8")
                ams_access_log.keysReturned = str(key_record.id)
                session.commit()

                session.query(AMS_Keys).filter(
                    AMS_Keys.peg_id == ams_can2.key_inserted_id
                ).update(
                    {
                        "current_pos_door_id": 1,
                        "keyTakenBy": None,
                        "keyTakenAtTime": None,
                        "current_pos_strip_id": ams_can2.key_inserted_position_list,
                        "current_pos_slot_no": ams_can2.key_inserted_position_slot,
                        "keyStatus": SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT,
                    }
                )
                session.commit()

                ams_event_log = AMS_Event_Log(
                    userId=user_auth["id"],
                    keyId=key_record.id,
                    activityId=None,
                    eventId=EVENT_KEY_RETURNED_RIGHT_SLOT,
                    loginType="PIN",
                    access_log_id=ams_access_log.id,
                    timeStamp=datetime.now(tz_IN),
                    event_type=EVENT_TYPE_EVENT,
                    is_posted=0,
                )
                session.add(ams_event_log)
                session.commit()
                show_msg_on_display(
                    lib_display, msg1=None, msg2=keys_msg_print, sleep_duration=None
                )
                ams_can2.key_inserted_event = False
                if key_record.keyName not in keys_returned_list:
                    keys_returned_list.append(key_record.keyName)

            elif (
                key_record.keyStrip != ams_can2.key_inserted_position_list
                or key_record.keyPosition != ams_can2.key_inserted_position_slot
            ):
                ams_can2.set_single_LED_state(
                    ams_can2.key_inserted_position_list,
                    ams_can2.key_inserted_position_slot,
                    CAN_LED_STATE_BLINK,
                )
                keys_msg_print = (
                    "Key return:" + (key_record.keyName.ljust(4, " "))
                ).encode("utf-8")

                print("in wrong condition ", end="")
                print(keys_msg_print)

                ams_access_log.keysReturned = str(key_record.id)
                session.commit()

                session.query(AMS_Keys).filter(
                    AMS_Keys.peg_id == ams_can2.key_inserted_id
                ).update(
                    {
                        "current_pos_door_id": 1,
                        "current_pos_strip_id": ams_can2.key_inserted_position_list,
                        "current_pos_slot_no": ams_can2.key_inserted_position_slot,
                        "keyStatus": SLOT_STATUS_KEY_PRESENT_WRONG_SLOT,
                    }
                )
                session.commit()

                ams_event_log = AMS_Event_Log(
                    userId=user_auth["id"],
                    keyId=key_record.id,
                    activityId=None,
                    eventId=EVENT_KEY_RETURNED_WRONG_SLOT,
                    loginType="PIN",
                    access_log_id=ams_access_log.id,
                    timeStamp=datetime.now(tz_IN),
                    event_type=EVENT_TYPE_EVENT,
                    is_posted=0,
                )
                session.add(ams_event_log)
                session.commit()
                show_msg_on_display(
                    lib_display, msg1=None, msg2=keys_msg_print, sleep_duration=None
                )

                ams_can2.key_inserted_event = False
                IS_KEY_IN_WRONG_SLOT = True

                if not ams_can2.get_key_id(key_record.keyStrip, key_record.keyPosition):
                    ams_can2.set_single_key_lock_state(
                        ams_can2.key_inserted_position_list,
                        ams_can2.key_inserted_position_slot,
                        CAN_KEY_UNLOCKED,
                    )
                    ams_can2.set_single_LED_state(
                        ams_can2.key_inserted_position_list,
                        ams_can2.key_inserted_position_slot,
                        CAN_LED_STATE_BLINK,
                    )
                    ams_can2.set_single_key_lock_state(
                        key_record.keyStrip, key_record.keyPosition, CAN_KEY_UNLOCKED
                    )
                    ams_can2.set_single_LED_state(
                        key_record.keyStrip, key_record.keyPosition, CAN_LED_STATE_ON
                    )

                    correct_key_POS = key_record.keyPosition + (
                        (key_record.keyStrip - 1) * 14
                    )
                    current_key_POS = ams_can2.key_inserted_position_slot + (
                        (ams_can2.key_inserted_position_list - 1) * 14
                    )
                    msg_line1 = ("Wrong slot  " + str(current_key_POS) + "  ").encode(
                        "utf-8"
                    )
                    msg_line2 = ("Put in slot " + str(correct_key_POS) + "  ").encode(
                        "utf-8"
                    )
                    show_msg_on_display(
                        lib_display, msg1=msg_line1, msg2=msg_line2, sleep_duration=None
                    )

                    if key_record.id not in keys_returned_list:
                        keys_returned_list.append(key_record.id)
                    if key_record.id in keys_taken_list:
                        keys_taken_list.remove(key_record.id)
                else:
                    msg_line1 = "Key in wrong pos".encode("utf-8")
                    msg_line2 = "Correct pos n/a ".encode("utf-8")
                    show_msg_on_display(
                        lib_display, msg1=msg_line1, msg2=msg_line2, sleep_duration=None
                    )

                IS_KEY_IN_WRONG_SLOT_Correct_Strip = key_record.keyStrip
                IS_KEY_IN_WRONG_SLOT_Correct_Pos = key_record.keyPosition
                IS_KEY_IN_WRONG_SLOT_Wrong_Strip = ams_can2.key_inserted_position_list
                IS_KEY_IN_WRONG_SLOT_Wrong_Pos = ams_can2.key_inserted_position_slot
                IS_KEY_IN_WRONG_SLOT_User_PIN = None
                lib_Buzzer.setBuzzerOn()
                sleep(5)
                lib_Buzzer.setBuzzerOff()
                if key_record.keyName not in keys_returned_list:
                    keys_returned_list.append(key_record.keyName)

        else:
            print("Key inserted but key record not found for updating inserted event")
            msg_line1 = "Key record n/a  ".encode("utf-8")
            msg_line2 = "Register the key".encode("utf-8")
            show_msg_on_display(
                lib_display, msg1=msg_line1, msg2=msg_line2, sleep_duration=1
            )


def print_on_display(header, lib_display):
    lib_display.displayClear()
    sleep(0.2)
    current_head = header
    for i in range(2):
        if current_head:
            lib_display.displayString(current_head.instance_name.encode("utf-8"), i + 1)
            current_head = current_head.next


def select_key(session, lib_display, lib_keypad, FD_KEYPAD):
    keys = session.query(AMS_Keys).all()
    instance_names = map(lambda x: x.keyName, keys)

    def select_particular_key(instance_names, lib_keypad):
        my_list = InstanceDoublyLinkedList()
        keys = instance_names

        for key in keys:
            my_list.append(key)
        print(f"there are all {my_list.length()} keys present in the cabinet")

        selected_key = None
        header = my_list.head
        print_on_display(header, lib_display)
        while True:
            print()
            key = lib_keypad.keypadHandler(FD_KEYPAD)
            in_data = str(KEY_DICT[str(key)])
            # up
            if in_data == "UP":
                print("up")
                if header.prev:
                    header = header.prev
                    print_on_display(header, lib_display)
                else:
                    print_on_display(header, lib_display)
            # down
            elif in_data == "DN":
                print("down")
                if header.next:
                    header = header.next
                    print_on_display(header, lib_display)
                else:
                    print_on_display(header, lib_display)
            # select this
            elif in_data == "ENTER":
                print("enetered")
                selected_key = header.instance_name
                break
            # wrong input
            else:
                print("select proper input")

        print(f"*********** you have selected {selected_key} ************")
        return selected_key

    key_selected = select_particular_key(instance_names, lib_keypad)
    return key_selected


def quit_function(fn_name):
    # print to stderr, unbuffered in Python 2.
    print("\n\tTIMEOUT!!! Press any key", file=sys.stderr)
    # sys.stderr.flush()
    thread.interrupt_main()  # raises KeyboardInterrupt


def exit_after(s):
    """
    use as decorator to exit process if
    function takes longer than s seconds
    """

    def outer(fn):
        def inner(*args, **kwargs):
            timer = threading.Timer(s, quit_function, args=[fn.__name__])
            timer.start()
            try:
                result = fn(*args, **kwargs)
            finally:
                timer.cancel()
            return result

        return inner

    return outer


# @exit_after(10)
def get_option(prompt, options):
    while True:
        option = int(input(prompt))
        if not option:
            print("Please enter an option.")
            continue
        if str(option) not in options:
            valid_options = ", ".join(options)
            print("Invalid option. Valid options: " + valid_options)
            continue
        else:
            return option


@exit_after(60)
def login_using_PIN(lib_display, lib_keypad, FD_KEYPAD):
    pin_char_count = 0
    pin_entered = ""
    while pin_char_count < 5:
        key = lib_keypad.keypadHandler(FD_KEYPAD)
        key_str = str(KEY_DICT[str(key)])
        if key is not None:
            if key_str.isnumeric():
                pin_entered = pin_entered + key_str
                lib_display.displayStringWithPosition(
                    "*".encode("utf-8"), 2, 10 + pin_char_count
                )
                pin_char_count = pin_char_count + 1
            elif key_str == "ENTER":
                return pin_entered
            elif key_str == "ESC":
                return ""
    return pin_entered


@exit_after(60)
def login_using_PIN_Card_Bio(lib_display, lib_keypad, FD_KEYPAD, lib_battery, session):

    pin_char_count = 0
    pin_entered = ""
    Card_No = 0
    login_option = ""
    login_option_str = ""

    show_msg_on_display(
        lib_display,
        msg1="Press 1 for Card",
        msg2="Press 2 for Bio",
        sleep_duration=None,
    )

    login_option = lib_keypad.keypadHandler(FD_KEYPAD)
    login_option_str = str(KEY_DICT[str(login_option)])

    if login_option_str == "1":

        show_msg_on_display(
            lib_display, msg1="Show your card", msg2=None, sleep_duration=None
        )
        timer_sec = 0

        while True:
            timer_sec += 1
            sleep(1)
            Card_No = lib_battery.getCardDetails()
            print(f"card number is: {Card_No}")
            if Card_No > 0 or timer_sec > 15:
                break

        if Card_No > 0:
            show_msg_on_display(
                lib_display,
                msg1="             ",
                msg2="Enter PIN: ",
                sleep_duration=None,
            )
            while pin_char_count < 5:
                key = lib_keypad.keypadHandler(FD_KEYPAD)
                key_str = str(KEY_DICT[str(key)])
                if key_str.isnumeric():
                    pin_entered = pin_entered + key_str
                    lib_display.displayStringWithPosition(
                        "*".encode("utf-8"), 2, 10 + pin_char_count
                    )
                    pin_char_count = pin_char_count + 1
                elif key_str == "ENTER":
                    return AUTH_MODE_CARD_PIN, pin_entered, Card_No
                elif key_str == "F1":
                    return AUTH_MODE_CARD_PIN, "", Card_No
            return AUTH_MODE_CARD_PIN, pin_entered, Card_No
        else:
            show_msg_on_display(
                lib_display, msg1="TIMEOUT !!!", msg2=None, sleep_duration=2
            )
            return AUTH_MODE_CARD_PIN, "", 0

    elif login_option_str == "2":
        show_msg_on_display(
            lib_display, msg1="Scan finger now ", msg2=None, sleep_duration=None
        )
        if os.path.exists("frame_Ex.bmp"):
            os.remove("frame_Ex.bmp")

        if os.path.exists("user_template"):
            os.remove("user_template")
        print("VERIFICATION STEP: PLease place finger on scanner...")

        return_val = subprocess.run("/home/ams-core/ftrScanAPI_Ex")

        print("Return value from ftrScanAPI : " + str(return_val))

        enroll_data = subprocess.run(
            [
                "/home/ams-core/FCEnrollFingerFromImageCPP",
                "frame_Ex.bmp",
                "user_template",
            ]
        )
        lib_display.displayString("Scan ok pls wait".encode("utf-8"), 2)
        recordset = session.query(AMS_Users).all()
        if recordset:
            for rows in recordset:
                with open("reference_file", "wb") as f:
                    f.write(rows.fpTemplate)
                stdout = subprocess.run(
                    [
                        "/home/ams-core/FCIdentifyFingerCPP",
                        "user_template",
                        "reference_file",
                    ],
                    capture_output=True,
                    text=True,
                ).stdout
                print("###### VERIFICATION METHOD CALLED ########")
                int_score = None
                for line in stdout.splitlines():
                    if "Identification score:" in line:
                        str_score = (line[21:]).strip()
                        if str_score.isnumeric():
                            int_score = int(str_score)
                if int_score:
                    if int_score > 96:
                        pin_entered = rows.pinCode
                        return AUTH_MODE_BIO, pin_entered, 0
                    else:
                        return AUTH_MODE_BIO, "", 0
                else:
                    return AUTH_MODE_BIO, "", 0
        else:
            return AUTH_MODE_BIO, "", 0
    else:
        return 0, "", 0

@exit_after(60)
def get_activity_code(lib_display, lib_keypad, FD_KEYPAD):
    act_char_count = 0
    act_code_entered = ""
    while act_char_count < 2:
        key = lib_keypad.keypadHandler(FD_KEYPAD)
        key_str = str(KEY_DICT[str(key)])
        if key is not None:
            if key_str.isnumeric():
                act_code_entered = act_code_entered + key_str
                lib_display.displayStringWithPosition(
                    "*".encode("utf-8"), 2, 14 + act_char_count
                )
                act_char_count = act_char_count + 1
        elif key_str == "ENTER":
            return act_code_entered
        elif key_str == "ESC":
            return ""
    return act_code_entered

def ams_header_line(session, lib_battery):
    ams_alarm_count = (
        session.query(AMS_Event_Log).filter(AMS_Event_Log.event_type == 2).count()
    )
    print("Alarm Count = " + str(ams_alarm_count))
    bcp = lib_battery.getBatteryPercentage()
    ams_header_line_str = "Alarm " + str(ams_alarm_count) + " Bat" + str(bcp) + "%"
    return ams_header_line_str

def update_keys_status(ams_can, list_ID, session):

    for key_num in range(1, 15):
        key_id = ams_can.get_key_id(list_ID, key_num)
        if key_id:
            print("Key number:" + str(key_num))
            session.query(AMS_Keys).filter(AMS_Keys.peg_id == key_id).update(
                {
                    "current_pos_strip_id": list_ID,
                    "current_pos_slot_no": key_num,
                    "keyStatus": SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT,
                }
            )

            session.commit()
            session.query(AMS_Keys).filter(AMS_Keys.peg_id == key_id).filter(
                (AMS_Keys.keyStrip == list_ID)
                & (AMS_Keys.current_pos_slot_no == (key_num))
            ).update({"keyStatus": SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT})
            session.commit()
            session.query(AMS_Keys).filter(AMS_Keys.peg_id == key_id).filter(
                (AMS_Keys.keyStrip != list_ID)
                | (AMS_Keys.current_pos_slot_no != (key_num))
            ).update({"keyStatus": SLOT_STATUS_KEY_PRESENT_WRONG_SLOT})
            session.commit()
        else:
            session.query(AMS_Keys).filter(
                AMS_Keys.current_pos_strip_id == list_ID
            ).filter(AMS_Keys.current_pos_slot_no == (key_num)).update(
                {"keyStatus": SLOT_STATUS_KEY_NOT_PRESENT}
            )
            session.commit()

def show_error_msgs(lib_display, lib_Buzzer, msg1="ERROR OCCURED", msg2=None):
    lib_Buzzer.setBuzzerOn()
    show_msg_on_display(lib_display, msg1=msg1, msg2=msg2, sleep_duration=2)
    lib_Buzzer.setBuzzerOff()

def show_msg_on_display(lib_display, msg1=None, msg2=None, sleep_duration=0.5):
    lib_display.displayClear()
    if msg1:
        lib_display.displayString(msg1.encode("utf-8"), 1)
    if msg2:
        lib_display.displayString(msg2.encode("utf-8"), 2)
    if sleep_duration:
        sleep(sleep_duration)
        lib_display.displayClear()

def main():

    tz_IN = pytz.timezone("Asia/Kolkata")
    IS_KEY_IN_WRONG_SLOT = None
    IS_KEY_IN_WRONG_SLOT_Correct_Strip = None
    IS_KEY_IN_WRONG_SLOT_Correct_Pos = None
    IS_KEY_IN_WRONG_SLOT_Wrong_Strip = None
    IS_KEY_IN_WRONG_SLOT_Wrong_Pos = None
    IS_KEY_IN_WRONG_SLOT_User_PIN = None
    IS_KEY_IN_WRONG_SLOT_Message = None

    ams_cabinet = AMS_Cabinet()
    ams_event_types = AMS_Event_Types()
    ams_access_log = None
    ams_event_log = None
    ams_user = AMS_Users()
    ams_can = None
    ams_alarm_count = 0

    # Initialize hardware peripherals

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

    lib_battery = ctypes.CDLL("libBattery.so")
    lib_battery.getBatteryPercentage.argtypes = []
    lib_battery.bmsInit.argtypes = []
    lib_battery.getCardDetails.argtypes = []
    lib_battery.getCardDetails.restype = ctypes.c_ulonglong

    lib_battery.bmsInit()
    sleep(1)
    BATTERY_CHARGE_PC = None

    lib_keypad = ctypes.CDLL("libKeypad.so")
    lib_keypad.keypadInit.argtypes = []
    lib_keypad.keypadHandler.argtypes = [ctypes.c_int]
    lib_keypad.keypadClose.argtypes = [ctypes.c_int]
    FD_KEYPAD = lib_keypad.keypadInit()

    lib_KeyboxLock = ctypes.CDLL("libKeyboxLock.so")
    lib_KeyboxLock.getDoorSensorStatus1.argtypes = []
    lib_KeyboxLock.setKeyBoxLock.argtypes = [ctypes.c_int]
    lib_KeyboxLock.getDoorSensorStatus1.argtypes = []

    # initializing engine/connection and session to handle CRUD operations
    try:
        engine = create_engine("sqlite:////home/ams-core/csiams.dev.sqlite")
        Session = sessionmaker()
        Session.configure(bind=engine)
        session = Session()
    except Exception as e:
        print(e)
        print("error occured during conneting to sqlite database!")
        show_error_msgs(lib_display, lib_Buzzer, msg2="SQLite DataBase")

    # under testing
    #
    # key_selected = select_key(session, lib_display, lib_keypad, FD_KEYPAD)
    # lib_display.displayString(key_selected.encode('utf-8'), 1)
    # lib_display.displayString('selected key'.encode('utf-8'), 2)
    # sleep(3)
    # lib_display.displayClear()
    #
    # under testing

    current_date = datetime.now(tz_IN).strftime("%d-%m-%Y %H:%M")

    try:
        cabinet = session.query(AMS_Cabinet).one_or_none()
    except Exception as e:
        print(e)
        print("multiple records of ams cabinet found!")
        show_error_msgs(lib_display, lib_Buzzer, msg2="Multiple Cabs")
        cabinet = session.query(AMS_Cabinet).filter(AMS_Cabinet.id == 1).one_or_none()

    if cabinet:

        BATTERY_CHARGE_PC = lib_battery.getBatteryPercentage()

        show_msg_on_display(
            lib_display, msg1="Powered By CSI", msg2=None, sleep_duration=2
        )
        show_msg_on_display(
            lib_display, msg1="WELCOME AMS V1.1", msg2=current_date, sleep_duration=2
        )

        battery_pc_msg = "Battery Chrg:" + str(BATTERY_CHARGE_PC) + "%"
        show_msg_on_display(
            lib_display, msg1=battery_pc_msg, msg2=None, sleep_duration=2
        )

        ams_can = AMS_CAN()
        strip_version = ams_can.get_version_number(1)
        strip_version = ams_can.get_version_number(2)
        sleep(2)

        ams_can = AMS_CAN()
        sleep(6)
        strip_version = ams_can.get_version_number(1)
        strip_version = ams_can.get_version_number(2)

        ams_event_logs = AMS_Event_Log()
        print("\n\nNo of key-lists : " + str(len(ams_can.key_lists)))
        for keys in ams_can.key_lists:
            print("Key-list Id : " + str(keys))

        show_msg_on_display(
            lib_display, msg1="WELCOME AMS V1.1", msg2=current_date, sleep_duration=None
        )

        for keylistid in ams_can.key_lists:
            ams_can.unlock_all_positions(keylistid)
            ams_can.set_all_LED_OFF(keylistid)
        pegs_verified = False

        try:
            is_activity = (
                session.query(AMS_Activity_Progress_Status)
                .filter(AMS_Activity_Progress_Status.id == 1)
                .one_or_none()
            )
        except Exception as e:
            is_activity = None
            print(e)

        while True:
            print("############   Step 1  ###########")
            try:
                print("\n** 2")
                print(cabinet.site)

                header_line = ams_header_line(session, lib_battery)
                current_date = datetime.now(tz_IN).strftime("%d-%m-%Y %H:%M")
                show_msg_on_display(
                    lib_display,
                    msg1=header_line,
                    msg2=current_date,
                    sleep_duration=None,
                )

                login_msg = (
                    "Site: "
                    + cabinet.site.siteName
                    + (" " * int(10 - len(cabinet.site.siteName)))
                )

                # if not pegs_verified:
                show_msg_on_display(
                    lib_display,
                    msg1=header_line,
                    msg2="Please Wait.....",
                    sleep_duration=None,
                )
                for lists in ams_can.key_lists:
                    update_keys_status(ams_can, lists, session)
                pegs_verified = True
                show_msg_on_display(
                    lib_display, msg1=header_line, msg2=login_msg, sleep_duration=None
                )

                for keylistid in ams_can.key_lists:
                    ams_can.unlock_all_positions(keylistid)
                    ams_can.set_all_LED_OFF(keylistid)

                if is_activity:
                    is_activity.is_active = 0
                    session.commit()

                key_str = ""
                key = lib_keypad.keypadHandler(FD_KEYPAD)
                key_str = str(KEY_DICT[str(key)])
                user_auth = None

                if key_str == "ENTER":

                    if is_activity:
                        is_activity.is_active = 1
                        session.commit()

                    print("############   Step 2  ###########")
                    try:

                        auth_mode, pin_entered, card_swiped = login_using_PIN_Card_Bio(
                            lib_display, lib_keypad, FD_KEYPAD, lib_battery, session
                        )
                        print(
                            "Auto mode :"
                            + str(auth_mode)
                            + " pin_entered = "
                            + str(pin_entered)
                            + " card no : "
                            + str(card_swiped)
                        )

                        if auth_mode > 0:
                            user_auth = ams_user.get_user_id(
                                session,
                                auth_mode,
                                pin_no=pin_entered,
                                card_no=card_swiped,
                            )
                        else:
                            continue

                        if user_auth["ResultCode"] == AUTH_RESULT_SUCCESS:
                            print("############   Step 3  ###########")
                            user = (
                                session.query(AMS_Users)
                                .filter(
                                    and_(
                                        AMS_Users.pinCode == pin_entered,
                                        AMS_Users.cardNo == str(card_swiped),
                                    )
                                )
                                .one_or_none()
                            )
                            user.lastLoginDate = datetime.now(tz_IN)
                            session.commit()

                            user_str = (
                                ("Hi " + (user_auth["name"])[0:12])
                                .ljust(15, " ")
                                .encode("utf-8")
                            )

                            lib_display.displayStringWithPosition(user_str, 2, 0)
                            sleep(2)

                            ams_access_log = AMS_Access_Log(
                                signInTime=datetime.now(tz_IN),
                                signInMode=AUTH_MODE_PIN,
                                signInFailed=0,
                                signInSucceed=1,
                                signInUserId=user_auth["id"],
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

                            ams_event_log = AMS_Event_Log(
                                userId=user_auth["id"],
                                keyId=None,
                                activityId=None,
                                eventId=EVENT_LOGIN_SUCCEES,
                                loginType="PIN",
                                access_log_id=ams_access_log.id,
                                timeStamp=datetime.now(tz_IN),
                                event_type=EVENT_TYPE_EVENT,
                                is_posted=0,
                            )
                            session.add(ams_event_log)
                            session.commit()
                        else:
                            user_str = (
                                str(user_auth["Message"]).ljust(16, " ").encode("utf-8")
                            )
                            lib_display.displayStringWithPosition(user_str, 2, 0)
                            sleep(3)

                            ams_access_log = AMS_Access_Log(
                                signInTime=datetime.now(tz_IN),
                                signInMode=AUTH_MODE_PIN,
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

                            ams_event_log = AMS_Event_Log(
                                userId=0,
                                keyId=None,
                                activityId=None,
                                eventId=EVENT_LOGIN_FAILED,
                                loginType="PIN",
                                access_log_id=ams_access_log.id,
                                timeStamp=datetime.now(tz_IN),
                                event_type=EVENT_TYPE_ALARM,
                                is_posted=0,
                            )
                            session.add(ams_event_log)
                            session.commit()
                            continue

                        if user_auth["ResultCode"] == AUTH_RESULT_SUCCESS:
                            print("############   Step 4  ###########")
                            try:
                                print("############   Step 5  ###########")
                                show_msg_on_display(
                                    lib_display,
                                    msg1=None,
                                    msg2="Activity Code:",
                                    sleep_duration=None,
                                )
                                act_code_entered = get_activity_code(
                                    lib_display, lib_keypad, FD_KEYPAD
                                )
                                ams_activities = AMS_Activities()
                                dic_result = ams_activities.get_keys_allowed(
                                    session,
                                    user_auth["id"],
                                    act_code_entered,
                                    datetime.now(tz_IN),
                                )

                                if dic_result["ResultCode"] == ACTIVITY_ALLOWED:
                                    print("############   Step 6  ###########")
                                    allowed_keys_list = None
                                    allowed_keys_list = (
                                        dic_result["Message"].strip("][").split(",")
                                    )
                                    print(
                                        "\nAllowed Keys are : " + str(allowed_keys_list)
                                    )

                                    ams_access_log.activityCodeEntryTime = datetime.now(
                                        tz_IN
                                    )
                                    ams_access_log.activityCode = act_code_entered
                                    ams_access_log.event_type_id = EVENT_TYPE_EVENT
                                    session.commit()

                                    ams_event_log = AMS_Event_Log(
                                        userId=user_auth["id"],
                                        keyId=None,
                                        activityId=act_code_entered,
                                        eventId=EVENT_ACTIVITY_CODE_CORRECT,
                                        loginType="PIN",
                                        access_log_id=ams_access_log.id,
                                        timeStamp=datetime.now(tz_IN),
                                        event_type=EVENT_TYPE_EVENT,
                                        is_posted=0,
                                    )
                                    session.add(ams_event_log)
                                    session.commit()

                                    keys_OUT_STATUS_list = []
                                    keys_IN_STATUS_List = []
                                    keys_msg_In = "[IN :"
                                    keys_msg_Out = "[OUT:"
                                    key_record_list = []

                                    print("Keys allowed: " + str(allowed_keys_list))
                                    print("Cabinet Keys: " + str(len(cabinet.keys)))

                                    ams_can.lock_all_positions(1)
                                    sleep(0.2)
                                    ams_can.lock_all_positions(2)

                                    for keys in allowed_keys_list:
                                        print("############   Step 7  ###########")
                                        key_record = None
                                        key_slot_no = 0
                                        for key_rec in cabinet.keys:
                                            print("key_rec.id " + str(key_rec.id))
                                            print("keys " + str(keys))
                                            if str(key_rec.id) == str(keys):
                                                key_record = key_rec
                                                if key_record:
                                                    if (
                                                        key_record.keyStatus
                                                        == SLOT_STATUS_KEY_NOT_PRESENT
                                                    ):
                                                        key_slot_no = (
                                                            key_record.keyPosition
                                                            + (
                                                                (
                                                                    key_record.keyStrip
                                                                    - 1
                                                                )
                                                                * 14
                                                            )
                                                        )
                                                        keys_OUT_STATUS_list.append(
                                                            key_record.id
                                                        )
                                                        keys_msg_Out = (
                                                            keys_msg_Out
                                                            + " K"
                                                            + str(key_slot_no)
                                                        )

                                                        if not ams_can.get_key_id(
                                                            key_record.keyStrip,
                                                            key_record.keyPosition,
                                                        ):
                                                            ams_can.set_single_key_lock_state(
                                                                key_record.keyStrip,
                                                                key_record.keyPosition,
                                                                CAN_KEY_UNLOCKED,
                                                            )
                                                            ams_can.set_single_LED_state(
                                                                key_record.keyStrip,
                                                                key_record.keyPosition,
                                                                CAN_LED_STATE_ON,
                                                            )
                                                        else:
                                                            print(
                                                                "\nAnother Key already present in the slot!!!! "
                                                            )

                                                    elif (
                                                        key_record.keyStatus
                                                        == SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT
                                                    ):
                                                        key_slot_no = (
                                                            key_record.keyPosition
                                                            + (
                                                                (
                                                                    key_record.keyStrip
                                                                    - 1
                                                                )
                                                                * 14
                                                            )
                                                        )
                                                        keys_IN_STATUS_List.append(
                                                            key_record.id
                                                        )
                                                        keys_msg_In = (
                                                            keys_msg_In
                                                            + " K"
                                                            + str(key_slot_no)
                                                        )

                                                        ams_can.set_single_key_lock_state(
                                                            key_record.current_pos_strip_id,
                                                            key_record.current_pos_slot_no,
                                                            CAN_KEY_UNLOCKED,
                                                        )
                                                        ams_can.set_single_LED_state(
                                                            key_record.current_pos_strip_id,
                                                            key_record.current_pos_slot_no,
                                                            CAN_LED_STATE_ON,
                                                        )

                                                    elif (
                                                        key_record.keyStatus
                                                        == SLOT_STATUS_KEY_PRESENT_WRONG_SLOT
                                                    ):
                                                        key_slot_no = (
                                                            key_record.keyPosition
                                                            + (
                                                                (
                                                                    key_record.keyStrip
                                                                    - 1
                                                                )
                                                                * 14
                                                            )
                                                        )
                                                        keys_IN_STATUS_List.append(
                                                            key_record.id
                                                        )
                                                        keys_msg_In = (
                                                            keys_msg_In
                                                            + " K"
                                                            + str(key_slot_no)
                                                        )

                                                        ams_can.set_single_key_lock_state(
                                                            key_record.current_pos_strip_id,
                                                            key_record.current_pos_slot_no,
                                                            CAN_KEY_UNLOCKED,
                                                        )
                                                        ams_can.set_single_LED_state(
                                                            key_record.current_pos_strip_id,
                                                            key_record.current_pos_slot_no,
                                                            CAN_LED_STATE_BLINK,
                                                        )

                                                    break

                                    print("############   Step 8  ###########")
                                    keys_msg_In = keys_msg_In + "]"
                                    keys_msg_Out = keys_msg_Out + "]"
                                    msg_line_1 = (keys_msg_In + keys_msg_Out)[:16]
                                    msg_line_2 = (keys_msg_In + keys_msg_Out)[16:]
                                    show_msg_on_display(
                                        lib_display,
                                        msg1=msg_line_1,
                                        msg2=msg_line_2,
                                        sleep_duration=None,
                                    )

                                    lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_UN_LOCK)
                                    ams_access_log.doorOpenTime = datetime.now(tz_IN)
                                    ams_access_log.event_type_id = EVENT_TYPE_EVENT
                                    session.commit()

                                    ams_event_log = AMS_Event_Log(
                                        userId=user_auth["id"],
                                        keyId=None,
                                        activityId=act_code_entered,
                                        eventId=EVENT_DOOR_OPEN,
                                        loginType="PIN",
                                        access_log_id=ams_access_log.id,
                                        timeStamp=datetime.now(tz_IN),
                                        event_type=EVENT_TYPE_EVENT,
                                        is_posted=0,
                                    )
                                    session.add(ams_event_log)
                                    session.commit()

                                    sec_counter = 0
                                    door_is_open = False
                                    while True:
                                        print("############   Step 9  ###########")
                                        door_status = (
                                            lib_KeyboxLock.getDoorSensorStatus1()
                                        )
                                        sleep(1)
                                        sec_counter += 1
                                        if door_status == 0:
                                            door_is_open = True
                                            break
                                        elif door_status == 1:
                                            door_is_open = False
                                        if sec_counter >= 5:
                                            break

                                    sec_counter = 0
                                    keys_taken_list = []
                                    keys_returned_list = []
                                    while door_is_open:

                                        print("############   Step 10  ###########")

                                        sec_counter += 1
                                        key_record = None

                                        if sec_counter == 5:
                                            lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                                        elif sec_counter >= 60:
                                            show_msg_on_display(
                                                lib_display,
                                                msg1="Door opened too ",
                                                msg2="long, close door",
                                                sleep_duration=2,
                                            )
                                            lib_Buzzer.setBuzzerOn()

                                        if ams_can.key_taken_event:
                                            print("############   Step 11  ###########")
                                            print("\n\nKEY INSERTED\n\n")
                                            for key in cabinet.keys:
                                                if key.peg_id == ams_can.key_taken_id:
                                                    key_record = key
                                            if key_record:
                                                keys_msg_print = (
                                                    "Key taken: "
                                                    + (key_record.keyName.ljust(4, " "))
                                                ).encode("utf-8")
                                                print(keys_msg_print)
                                                ams_access_log.keysTaken = str(
                                                    key_record.id
                                                )
                                                session.commit()
                                                session.query(AMS_Keys).filter(
                                                    AMS_Keys.peg_id
                                                    == ams_can.key_taken_id
                                                ).update(
                                                    {
                                                        "keyTakenBy": user_auth["id"],
                                                        "keyTakenByUser": user_auth[
                                                            "name"
                                                        ],
                                                        "current_pos_strip_id": ams_can.key_taken_position_list,
                                                        "current_pos_slot_no": ams_can.key_taken_position_slot,
                                                        "keyTakenAtTime": datetime.now(
                                                            tz_IN
                                                        ),
                                                        "keyStatus": SLOT_STATUS_KEY_NOT_PRESENT,
                                                    }
                                                )
                                                session.commit()

                                                ams_event_log = AMS_Event_Log(
                                                    userId=user_auth["id"],
                                                    keyId=key_record.id,
                                                    activityId=act_code_entered,
                                                    eventId=EVENT_KEY_TAKEN_CORRECT,
                                                    loginType="PIN",
                                                    access_log_id=ams_access_log.id,
                                                    timeStamp=datetime.now(tz_IN),
                                                    event_type=EVENT_TYPE_EVENT,
                                                    is_posted=0,
                                                )
                                                session.add(ams_event_log)
                                                session.commit()

                                                if (
                                                    key_record.keyName
                                                    not in keys_taken_list
                                                ):
                                                    keys_taken_list.append(
                                                        key_record.keyName
                                                    )

                                            else:
                                                print(
                                                    "Key taken but key record not found for updating taken event"
                                                )
                                                keys_msg_print = (
                                                    "Key not reg.    ".encode("utf-8")
                                                )

                                            show_msg_on_display(
                                                lib_display,
                                                msg1=None,
                                                msg2=keys_msg_print,
                                                sleep_duration=2,
                                            )
                                            ams_can.key_taken_event = False

                                        elif ams_can.key_inserted_event:
                                            print("############   Step 12  ###########")
                                            print("\n\nKEY INSERTED\n\n")
                                            for key in cabinet.keys:
                                                if (
                                                    key.peg_id
                                                    == ams_can.key_inserted_id
                                                ):
                                                    key_record = key

                                            if key_record:
                                                if (
                                                    key_record.keyStrip
                                                    == ams_can.key_inserted_position_list
                                                    and key_record.keyPosition
                                                    == ams_can.key_inserted_position_slot
                                                ):
                                                    ams_can.set_single_LED_state(
                                                        ams_can.key_inserted_position_list,
                                                        ams_can.key_inserted_position_slot,
                                                        CAN_LED_STATE_OFF,
                                                    )
                                                    keys_msg_print = (
                                                        "Key return:"
                                                        + (
                                                            key_record.keyName.ljust(
                                                                4, " "
                                                            )
                                                        )
                                                    ).encode("utf-8")
                                                    ams_access_log.keysReturned = str(
                                                        key_record.id
                                                    )
                                                    session.commit()

                                                    session.query(AMS_Keys).filter(
                                                        AMS_Keys.peg_id
                                                        == ams_can.key_inserted_id
                                                    ).update(
                                                        {
                                                            "current_pos_door_id": 1,
                                                            "keyTakenBy": None,
                                                            "keyTakenAtTime": None,
                                                            "current_pos_strip_id": ams_can.key_inserted_position_list,
                                                            "current_pos_slot_no": ams_can.key_inserted_position_slot,
                                                            "keyStatus": SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT,
                                                        }
                                                    )
                                                    session.commit()

                                                    ams_event_log = AMS_Event_Log(
                                                        userId=user_auth["id"],
                                                        keyId=key_record.id,
                                                        activityId=act_code_entered,
                                                        eventId=EVENT_KEY_RETURNED_RIGHT_SLOT,
                                                        loginType="PIN",
                                                        access_log_id=ams_access_log.id,
                                                        timeStamp=datetime.now(tz_IN),
                                                        event_type=EVENT_TYPE_EVENT,
                                                        is_posted=0,
                                                    )
                                                    session.add(ams_event_log)
                                                    session.commit()
                                                    show_msg_on_display(
                                                        lib_display,
                                                        msg1=None,
                                                        msg2=keys_msg_print,
                                                        sleep_duration=2,
                                                    )
                                                    ams_can.key_inserted_event = False
                                                    if (
                                                        key_record.keyName
                                                        not in keys_returned_list
                                                    ):
                                                        keys_returned_list.append(
                                                            key_record.keyName
                                                        )
                                                elif (
                                                    key_record.keyStrip
                                                    != ams_can.key_inserted_position_list
                                                    or key_record.keyPosition
                                                    != ams_can.key_inserted_position_slot
                                                ):
                                                    ams_can.set_single_LED_state(
                                                        ams_can.key_inserted_position_list,
                                                        ams_can.key_inserted_position_slot,
                                                        CAN_LED_STATE_BLINK,
                                                    )
                                                    keys_msg_print = (
                                                        "Key return:"
                                                        + (
                                                            key_record.keyName.ljust(
                                                                4, " "
                                                            )
                                                        )
                                                    ).encode("utf-8")

                                                    ams_access_log.keysReturned = str(
                                                        key_record.id
                                                    )
                                                    session.commit()

                                                    session.query(AMS_Keys).filter(
                                                        AMS_Keys.peg_id
                                                        == ams_can.key_inserted_id
                                                    ).update(
                                                        {
                                                            "current_pos_door_id": 1,
                                                            "current_pos_strip_id": ams_can.key_inserted_position_list,
                                                            "current_pos_slot_no": ams_can.key_inserted_position_slot,
                                                            "keyStatus": SLOT_STATUS_KEY_PRESENT_WRONG_SLOT,
                                                        }
                                                    )
                                                    session.commit()

                                                    ams_event_log = AMS_Event_Log(
                                                        userId=user_auth["id"],
                                                        keyId=key_record.id,
                                                        activityId=act_code_entered,
                                                        eventId=EVENT_KEY_RETURNED_WRONG_SLOT,
                                                        loginType="PIN",
                                                        access_log_id=ams_access_log.id,
                                                        timeStamp=datetime.now(tz_IN),
                                                        event_type=EVENT_TYPE_ALARM,
                                                        is_posted=0,
                                                    )
                                                    session.add(ams_event_log)
                                                    session.commit()
                                                    show_msg_on_display(
                                                        lib_display,
                                                        msg1=None,
                                                        msg2=keys_msg_print,
                                                        sleep_duration=2,
                                                    )
                                                    ams_can.key_inserted_event = False
                                                    IS_KEY_IN_WRONG_SLOT = True

                                                    if not ams_can.get_key_id(
                                                        key_record.keyStrip,
                                                        key_record.keyPosition,
                                                    ):
                                                        ams_can.set_single_key_lock_state(
                                                            ams_can.key_inserted_position_list,
                                                            ams_can.key_inserted_position_slot,
                                                            CAN_KEY_UNLOCKED,
                                                        )
                                                        ams_can.set_single_LED_state(
                                                            ams_can.key_inserted_position_list,
                                                            ams_can.key_inserted_position_slot,
                                                            CAN_LED_STATE_BLINK,
                                                        )
                                                        ams_can.set_single_key_lock_state(
                                                            key_record.keyStrip,
                                                            key_record.keyPosition,
                                                            CAN_KEY_UNLOCKED,
                                                        )
                                                        ams_can.set_single_LED_state(
                                                            key_record.keyStrip,
                                                            key_record.keyPosition,
                                                            CAN_LED_STATE_ON,
                                                        )

                                                        correct_key_POS = (
                                                            key_record.keyPosition
                                                            + (
                                                                (
                                                                    key_record.keyStrip
                                                                    - 1
                                                                )
                                                                * 14
                                                            )
                                                        )
                                                        current_key_POS = (
                                                            ams_can.key_inserted_position_slot
                                                            + (
                                                                (
                                                                    ams_can.key_inserted_position_list
                                                                    - 1
                                                                )
                                                                * 14
                                                            )
                                                        )
                                                        msg_line1 = (
                                                            "Wrong slot  "
                                                            + str(current_key_POS)
                                                            + "  "
                                                        ).encode("utf-8")
                                                        msg_line2 = (
                                                            "Put in slot "
                                                            + str(correct_key_POS)
                                                            + "  "
                                                        ).encode("utf-8")
                                                        show_msg_on_display(
                                                            lib_display,
                                                            msg1=msg_line1,
                                                            msg2=msg_line2,
                                                            sleep_duration=0.5,
                                                        )
                                                        if (
                                                            key_record.id
                                                            not in keys_returned_list
                                                        ):
                                                            keys_returned_list.append(
                                                                key_record.id
                                                            )
                                                        if (
                                                            key_record.id
                                                            in keys_taken_list
                                                        ):
                                                            keys_taken_list.remove(
                                                                key_record.id
                                                            )
                                                    else:
                                                        msg_line1 = (
                                                            "Key in wrong pos".encode(
                                                                "utf-8"
                                                            )
                                                        )
                                                        msg_line2 = (
                                                            "Correct pos n/a ".encode(
                                                                "utf-8"
                                                            )
                                                        )
                                                        show_msg_on_display(
                                                            lib_display,
                                                            msg1=msg_line1,
                                                            msg2=msg_line2,
                                                            sleep_duration=0.5,
                                                        )
                                                    IS_KEY_IN_WRONG_SLOT_Correct_Strip = (
                                                        key_record.keyStrip
                                                    )
                                                    IS_KEY_IN_WRONG_SLOT_Correct_Pos = (
                                                        key_record.keyPosition
                                                    )
                                                    IS_KEY_IN_WRONG_SLOT_Wrong_Strip = (
                                                        ams_can.key_inserted_position_list
                                                    )
                                                    IS_KEY_IN_WRONG_SLOT_Wrong_Pos = (
                                                        ams_can.key_inserted_position_slot
                                                    )
                                                    IS_KEY_IN_WRONG_SLOT_User_PIN = (
                                                        pin_entered
                                                    )
                                                    lib_Buzzer.setBuzzerOn()
                                                    sleep(5)
                                                    lib_Buzzer.setBuzzerOff()
                                                    if (
                                                        key_record.keyName
                                                        not in keys_returned_list
                                                    ):
                                                        keys_returned_list.append(
                                                            key_record.keyName
                                                        )

                                            else:
                                                print(
                                                    "Key inserted but key record not found for updating inserted event"
                                                )
                                                msg_line1 = "Key record n/a  ".encode(
                                                    "utf-8"
                                                )
                                                msg_line2 = "Register the key".encode(
                                                    "utf-8"
                                                )
                                                lib_display.displayClear()
                                                lib_display.displayString(msg_line1, 1)
                                                lib_display.displayString(msg_line2, 2)
                                                sleep(1)

                                        door_status = (
                                            lib_KeyboxLock.getDoorSensorStatus1()
                                        )
                                        sleep(1)
                                        if door_status == 0:
                                            door_is_open = True
                                        elif door_status == 1:
                                            door_is_open = False
                                    print("############   Step 13  ###########")
                                    lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                                    lib_Buzzer.setBuzzerOff()
                                    ams_can.lock_all_positions(1)
                                    ams_can.set_all_LED_OFF(1)
                                    ams_can.lock_all_positions(2)
                                    ams_can.set_all_LED_OFF(2)
                                    show_msg_on_display(
                                        lib_display,
                                        msg1=None,
                                        msg2="  Door Closed  ",
                                        sleep_duration=1,
                                    )

                                    ams_access_log.doorCloseTime = datetime.now(tz_IN)
                                    ams_access_log.keysAllowed = str(allowed_keys_list)
                                    ams_access_log.keysTaken = str(keys_taken_list)
                                    ams_access_log.keysReturned = str(
                                        keys_returned_list
                                    )
                                    ams_access_log.event_type_id = EVENT_TYPE_EVENT
                                    session.commit()

                                    ams_event_log = AMS_Event_Log(
                                        userId=user_auth["id"],
                                        keyId=None,
                                        activityId=act_code_entered,
                                        eventId=EVENT_DOOR_CLOSED,
                                        loginType="PIN",
                                        access_log_id=ams_access_log.id,
                                        timeStamp=datetime.now(tz_IN),
                                        event_type=EVENT_TYPE_EVENT,
                                        is_posted=0,
                                    )
                                    session.add(ams_event_log)
                                    session.commit()
                                    print("############   Step 14  ###########")
                                    if IS_KEY_IN_WRONG_SLOT:
                                        keys_msg = (
                                            "[S"
                                            + str(IS_KEY_IN_WRONG_SLOT_Wrong_Strip)
                                            + "P"
                                            + str(IS_KEY_IN_WRONG_SLOT_Wrong_Pos)
                                            + "]->[S"
                                            + str(IS_KEY_IN_WRONG_SLOT_Correct_Strip)
                                            + "P"
                                            + str(IS_KEY_IN_WRONG_SLOT_Correct_Pos)
                                            + "]"
                                        )
                                        IS_KEY_IN_WRONG_SLOT_Message = keys_msg
                                        show_msg_on_display(
                                            lib_display,
                                            msg1="Key in Wrong Pos",
                                            msg2=keys_msg,
                                            sleep_duration=2,
                                        )
                                        IS_KEY_IN_WRONG_SLOT = False
                                    continue
                                else:
                                    ams_event_log = AMS_Event_Log(
                                        userId=user_auth["id"],
                                        keyId=None,
                                        activityId=act_code_entered,
                                        eventId=EVENT_ACTIVITY_CODE_NOT_ALLOWED,
                                        loginType="PIN",
                                        access_log_id=ams_access_log.id,
                                        timeStamp=datetime.now(tz_IN),
                                        event_type=EVENT_TYPE_ALARM,
                                        is_posted=0,
                                    )
                                    session.add(ams_event_log)
                                    session.commit()
                                    print(
                                        "Activity Code not accepted: Reason - "
                                        + dic_result["Message"]
                                    )
                                    lib_display.displayString(
                                        (dic_result["Message"])
                                        .ljust(16, " ")
                                        .encode("utf-8"),
                                        2,
                                    )
                                    sleep(2)
                                    print("############   Step 15  ###########")
                                    continue

                            except KeyboardInterrupt:
                                print("############   Step 16  ###########")
                                print("Keyboard Interrupt!")
                                continue
                    except KeyboardInterrupt:
                        print("############   Step 17  ###########")
                        print("Keyboard Interrupt!")
                        continue
                elif key_str == "F1":

                    if is_activity:
                        is_activity.is_active = 1
                        session.commit()

                    print("############   Step 18  ###########")
                    show_msg_on_display(
                        lib_display, msg1=None, msg2="Admin PIN: ", sleep_duration=None
                    )
                    pin_entered = login_using_PIN(lib_display, lib_keypad, FD_KEYPAD)
                    print("pin Entered: " + str(pin_entered))
                    show_msg_on_display(
                        lib_display,
                        msg1=None,
                        msg2="Validating PIN..",
                        sleep_duration=None,
                    )

                    if not (pin_entered == ""):
                        print("############   Step 19  ###########")
                        user_auth = ams_user.get_user_id(
                            session, AUTH_MODE_PIN, pin_no=pin_entered
                        )
                        if user_auth["ResultCode"] == AUTH_RESULT_SUCCESS:
                            print("############   Step 20  ###########")
                            roleId = user_auth["roleId"]
                            if roleId == 1:
                                print("############   Step 21  ###########")
                                show_msg_on_display(
                                    lib_display,
                                    msg1="1. Reg. Card    ",
                                    msg2="2. Reg. Finger",
                                    sleep_duration=None,
                                )

                                key = lib_keypad.keypadHandler(FD_KEYPAD)
                                key_str = str(KEY_DICT[str(key)])
                                if key_str == "3":
                                    for keylistid in ams_can.key_lists:
                                        ams_can.unlock_all_positions(keylistid)
                                        ams_can.set_all_LED_ON(keylistid, False)

                                    show_msg_on_display(
                                        lib_display,
                                        msg1="                ",
                                        msg2="Open door...    ",
                                        sleep_duration=None,
                                    )
                                    lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_UN_LOCK)
                                    sec_counter = 0
                                    while True:
                                        print(
                                            "############   Waiting for Door to open  ###########"
                                        )
                                        door_status = (
                                            lib_KeyboxLock.getDoorSensorStatus1()
                                        )
                                        sleep(1)
                                        sec_counter += 1
                                        if door_status == 0 and sec_counter >= 5:
                                            lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                                            break
                                        if sec_counter > 5:
                                            lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                                            break
                                    if door_status == 1:
                                        for keylistid in ams_can.key_lists:
                                            ams_can.lock_all_positions(keylistid)
                                            ams_can.set_all_LED_OFF(keylistid)
                                        show_msg_on_display(
                                            lib_display,
                                            msg1="WELCOME AMS V1.1",
                                            msg2=None,
                                            sleep_duration=1,
                                        )
                                        continue

                                    show_msg_on_display(
                                        lib_display,
                                        msg1="Insert all keys",
                                        msg2="and press ENTER",
                                        sleep_duration=None,
                                    )

                                    key = lib_keypad.keypadHandler(FD_KEYPAD)
                                    key_str = str(KEY_DICT[str(key)])
                                    if key_str == "ENTER":
                                        show_msg_on_display(
                                            lib_display,
                                            msg1="Scan in progress",
                                            msg2="Pls Wait...     ",
                                            sleep_duration=None,
                                        )
                                        session.query(AMS_Key_Pegs).delete()
                                        session.commit()

                                        for keylistid in ams_can.key_lists:
                                            for slot in range(1, 15):
                                                ams_can.set_single_LED_state(
                                                    keylistid, slot, CAN_LED_STATE_BLINK
                                                )
                                                peg_id = None
                                                peg_id = ams_can.get_key_id(
                                                    keylistid, slot
                                                )

                                                if peg_id:
                                                    record = (
                                                        session.query(AMS_Key_Pegs)
                                                        .filter(
                                                            AMS_Key_Pegs.peg_id
                                                            == peg_id
                                                        )
                                                        .all()
                                                    )

                                                    key_pos_no = slot + (
                                                        (keylistid - 1) * 14
                                                    )

                                                    if record:
                                                        peg_display_msg = (
                                                            "Key "
                                                            + str(key_pos_no)
                                                            + " reg. done"
                                                        ).encode("utf-8")
                                                        show_msg_on_display(
                                                            lib_display,
                                                            msg1=None,
                                                            msg2=peg_display_msg,
                                                            sleep_duration=0.5,
                                                        )
                                                    else:
                                                        new_peg_id = AMS_Key_Pegs(
                                                            peg_id=peg_id,
                                                            keylist_no=keylistid,
                                                            keyslot_no=slot,
                                                        )
                                                        session.add(new_peg_id)
                                                        session.commit()

                                                        key = (
                                                            session.query(AMS_Keys)
                                                            .filter(
                                                                (
                                                                    AMS_Keys.keyStrip
                                                                    == int(keylistid)
                                                                )
                                                                & (
                                                                    AMS_Keys.keyPosition
                                                                    == int(slot)
                                                                )
                                                            )
                                                            .one_or_none()
                                                        )
                                                        print(key)
                                                        key.peg_id = peg_id
                                                        session.commit()

                                                        peg_display_msg = (
                                                            "Key "
                                                            + str(key_pos_no)
                                                            + " reg. done"
                                                        ).encode("utf-8")
                                                        show_msg_on_display(
                                                            lib_display,
                                                            msg1=None,
                                                            msg2=peg_display_msg,
                                                            sleep_duration=0.5,
                                                        )
                                                ams_can.set_single_LED_state(
                                                    keylistid, slot, CAN_LED_STATE_OFF
                                                )

                                    for keyid in ams_can.key_lists:
                                        ams_can.set_all_LED_ON(keyid, True)
                                        sleep(1)
                                        ams_can.lock_all_positions(keyid)
                                        sleep(1)
                                        ams_can.set_all_LED_OFF(keyid)
                                    show_msg_on_display(
                                        lib_display,
                                        msg1="WELCOME AMS V1.1",
                                        msg2=None,
                                        sleep_duration=1,
                                    )
                                    continue
                                elif key_str == "1":
                                    print("############   Step 22  ###########")
                                    show_msg_on_display(
                                        lib_display,
                                        msg1="Enter User PIN",
                                        msg2=None,
                                        sleep_duration=None,
                                    )
                                    pin_entered = login_using_PIN(
                                        lib_display, lib_keypad, FD_KEYPAD
                                    )
                                    show_msg_on_display(
                                        lib_display,
                                        msg1=None,
                                        msg2="Validating PIN..",
                                        sleep_duration=None,
                                    )
                                    print(f"entered pin is: {pin_entered}")
                                    if not (pin_entered == ""):
                                        user_auth = ams_user.get_user_id(
                                            session, AUTH_MODE_PIN, pin_no=pin_entered
                                        )
                                        if (
                                            user_auth["ResultCode"]
                                            == AUTH_RESULT_SUCCESS
                                        ):
                                            show_msg_on_display(
                                                lib_display,
                                                msg1="Swipe User Card",
                                                msg2=None,
                                                sleep_duration=None,
                                            )
                                            timer_sec = 0
                                            card_no = None
                                            card_no_updated = False
                                            while timer_sec < 30:
                                                timer_sec += 1
                                                card_no = lib_battery.getCardDetails()
                                                sleep(1)
                                                print(f"card number is: {card_no}")
                                                if card_no:
                                                    is_already_assigned = (
                                                        session.query(AMS_Users)
                                                        .filter(
                                                            AMS_Users.cardNo
                                                            == str(card_no)
                                                        )
                                                        .one_or_none()
                                                    )
                                                    if is_already_assigned:
                                                        show_msg_on_display(
                                                            lib_display,
                                                            msg1="Card Already",
                                                            msg2="Assigned",
                                                            sleep_duration=None,
                                                        )
                                                        card_no_updated = False
                                                        break
                                                    session.query(AMS_Users).filter(
                                                        AMS_Users.id == user_auth["id"]
                                                    ).update({"cardNo": str(card_no)})
                                                    card_no_updated = True
                                                    break

                                            if card_no_updated:
                                                msg = "for " + user_auth["name"]
                                                show_msg_on_display(
                                                    lib_display,
                                                    msg1="Card Registered",
                                                    msg2=msg,
                                                    sleep_duration=3,
                                                )
                                            else:
                                                show_msg_on_display(
                                                    lib_display,
                                                    msg1="Card not reg.",
                                                    msg2="Try again later.",
                                                    sleep_duration=3,
                                                )
                                            continue
                                elif key_str == "2":
                                    show_msg_on_display(
                                        lib_display,
                                        msg1="Enter User PIN",
                                        msg2=None,
                                        sleep_duration=None,
                                    )
                                    pin_entered = login_using_PIN(
                                        lib_display, lib_keypad, FD_KEYPAD
                                    )
                                    show_msg_on_display(
                                        lib_display,
                                        msg1=None,
                                        msg2="Validating PIN..",
                                        sleep_duration=None,
                                    )
                                    if not (pin_entered == ""):
                                        user_auth = ams_user.get_user_id(
                                            session, AUTH_MODE_PIN, pin_no=pin_entered
                                        )
                                        if (
                                            user_auth["ResultCode"]
                                            == AUTH_RESULT_SUCCESS
                                        ):
                                            show_msg_on_display(
                                                lib_display,
                                                msg1="Scan finger now",
                                                msg2=None,
                                                sleep_duration=None,
                                            )
                                            if os.path.exists("frame_Ex.bmp"):
                                                os.remove("frame_Ex.bmp")
                                                print("file removed")
                                            if os.path.exists("user_template"):
                                                os.remove("user_template")
                                                print("biometric file removed")

                                            print("PLease place finger on scanner...")

                                            return_val = subprocess.run(
                                                "/home/ams-core/ftrScanAPI_Ex"
                                            )

                                            print(
                                                "Return value from ftrScanAPI : "
                                                + str(return_val)
                                            )

                                            # Call FCEnrollFingerFromImageCPP and pass frame_Ex.bmp and user template name to generate template file
                                            show_msg_on_display(
                                                lib_display,
                                                msg1="Scan complete...",
                                                msg2="Saving, pls wait",
                                                sleep_duration=None,
                                            )

                                            enroll_data = subprocess.run(
                                                [
                                                    "/home/ams-core/FCEnrollFingerFromImageCPP",
                                                    "frame_Ex.bmp",
                                                    "user_template",
                                                ]
                                            )
                                            print(
                                                "enroll finger data: "
                                                + str(enroll_data)
                                            )

                                            with open("user_template", "rb") as f:
                                                ablob = f.read()

                                            session.query(AMS_Users).filter(
                                                AMS_Users.pinCode == pin_entered
                                            ).update({"fpTemplate": memoryview(ablob)})
                                            session.commit()
                                            show_msg_on_display(
                                                lib_display,
                                                msg1="FP registration",
                                                msg2="done, pls wait",
                                                sleep_duration=2,
                                            )
                                            continue
                                elif key_str == "F1":
                                    continue
                            else:
                                lib_display.displayString(
                                    "                ".encode("utf-8"), 2
                                )
                                lib_display.displayString(
                                    "User not admin!".encode("utf-8"), 2
                                )
                                sleep(2)
                                continue
                elif key_str == "F2":
                    if is_activity:
                        is_activity.is_active = 1
                        session.commit()

                    print("############   Step 19  ###########")
                    show_msg_on_display(
                        lib_display, msg1="Admin PIN:", msg2=None, sleep_duration=None
                    )
                    pin_entered = login_using_PIN(lib_display, lib_keypad, FD_KEYPAD)
                    show_msg_on_display(
                        lib_display,
                        msg1=None,
                        msg2="Validating PIN..",
                        sleep_duration=None,
                    )
                    user_auth = dict()
                    if not (pin_entered == ""):
                        if pin_entered == "36943":
                            user_auth = {
                                "ResultCode": AUTH_RESULT_SUCCESS,
                                "id": 1,
                                "name": "RO-Admin",
                                "roleId": 1,
                            }
                        else:
                            user_auth = {
                                "ResultCode": AUTH_RESULT_FAILED,
                                "id": 0,
                                "name": "",
                                "roleId": 0,
                            }
                        if user_auth["ResultCode"] == AUTH_RESULT_SUCCESS:
                            roleId = user_auth["roleId"]
                            if roleId == 1:
                                show_msg_on_display(
                                    lib_display,
                                    msg1=None,
                                    msg2="Take/Return Keys",
                                    sleep_duration=None,
                                )
                                ams_can.unlock_all_positions(1)
                                ams_can.set_all_LED_ON(1, False)

                                ams_can.unlock_all_positions(2)
                                ams_can.set_all_LED_ON(2, False)
                                lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_UN_LOCK)

                                ams_can.door_closed_status = False

                                print(f"user id is : {user_auth['id']}")

                                ams_access_log = AMS_Access_Log(
                                    signInTime=datetime.now(tz_IN),
                                    signInMode=AUTH_MODE_PIN,
                                    signInFailed=0,
                                    signInSucceed=1,
                                    signInUserId=user_auth["id"],
                                    activityCodeEntryTime=datetime.now(tz_IN),
                                    activityCode=1,
                                    doorOpenTime=datetime.now(tz_IN),
                                    keysAllowed=None,
                                    keysTaken=None,
                                    keysReturned=None,
                                    doorCloseTime=None,
                                    event_type_id=EVENT_DOOR_OPEN,
                                    is_posted=0,
                                )
                                session.add(ams_access_log)
                                session.commit()

                                ams_event_log = AMS_Event_Log(
                                    userId=user_auth["id"],
                                    keyId=None,
                                    activityId=1,
                                    eventId=EVENT_DOOR_OPEN,
                                    loginType="PIN",
                                    access_log_id=ams_access_log.id,
                                    timeStamp=datetime.now(tz_IN),
                                    event_type=EVENT_TYPE_EVENT,
                                    is_posted=0,
                                )
                                session.add(ams_event_log)
                                session.commit()

                                keys_taken_list = []
                                keys_returned_list = []
                                door_is_open = True
                                sec_counter = 0
                                while door_is_open:
                                    door_status = lib_KeyboxLock.getDoorSensorStatus1()
                                    print(f"door status is: {door_status}")
                                    sleep(1)
                                    sec_counter += 1
                                    if door_status == 0:
                                        door_is_open = True
                                    elif door_status == 1 and sec_counter >= 5:
                                        door_is_open = False
                                        break

                                    if sec_counter == 5:
                                        print(
                                            "inside threshold reached status!!!!!!!!!!!!"
                                        )
                                        lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                                        ams_can.door_closed_status = True

                                    get_key_interactions(
                                        ams_can,
                                        session,
                                        cabinet,
                                        ams_access_log,
                                        user_auth,
                                        lib_display,
                                        lib_Buzzer,
                                        keys_taken_list,
                                        keys_returned_list,
                                    )

                                    if sec_counter > 60:
                                        lib_display.displayClear()
                                        lib_display.displayString(
                                            "Door opened too ".encode("utf-8"), 1
                                        )
                                        lib_display.displayString(
                                            "long, close door".encode("utf-8"), 2
                                        )
                                        lib_Buzzer.setBuzzerOn()
                                        while True:
                                            door_status = (
                                                lib_KeyboxLock.getDoorSensorStatus1()
                                            )
                                            if door_status == 1:
                                                break
                                        break

                                lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                                lib_Buzzer.setBuzzerOff()
                                ams_can.lock_all_positions(1)
                                ams_can.set_all_LED_OFF(1)
                                ams_can.lock_all_positions(2)
                                ams_can.set_all_LED_OFF(2)
                                show_msg_on_display(
                                    lib_display,
                                    msg1=None,
                                    msg2="  Door Closed  ",
                                    sleep_duration=2,
                                )

                                ams_access_log.keysAllowed = ""
                                ams_access_log.keysTaken = str(keys_taken_list)
                                ams_access_log.keysReturned = str(keys_returned_list)
                                ams_access_log.event_type_id = EVENT_TYPE_EVENT
                                ams_access_log.doorCloseTime = datetime.now(tz_IN)
                                session.commit()

                                ams_event_log = AMS_Event_Log(
                                    userId=user_auth["id"],
                                    keyId=None,
                                    activityId=1,
                                    eventId=EVENT_DOOR_CLOSED,
                                    loginType="PIN",
                                    access_log_id=ams_access_log.id,
                                    timeStamp=datetime.now(tz_IN),
                                    event_type=EVENT_TYPE_EVENT,
                                    is_posted=0,
                                )
                                session.add(ams_event_log)
                                session.commit()

                                continue

            except Exception as e:
                ams_can.cleanup()
                lib_display.displayClose()
                lib_Buzzer.setBuzzerOff()
                if is_activity:
                    is_activity.is_active = 0
                    session.commit()
                session.close()
                for keylistid in ams_can.key_lists:
                    ams_can.unlock_all_positions(keylistid)
                    ams_can.set_all_LED_OFF(keylistid)
                print(f"Exited AMS-CORE app due to --> {e}")
    else:
        show_msg_on_display(
            lib_display, msg1=None, msg2="AMS not active! ", sleep_duration=None
        )
        session.close()
        return


if __name__ == "__main__":  
    main()
