from __future__ import print_function
import sys
import threading
import subprocess
import os
import amsbms
import ctypes
from ctypes import c_ulonglong
from time import sleep
from amsbms import *
import _thread as thread
from utils import show_msg_on_display, get_event_description, change_ip_address_gateway
from consts import EVENT_IP_ADDRESS_CHANGE_INITIALISED
DATE_SET=20
# try:
#     # for python 2
#     import thread
# except ImportError:
#     # for python 3
#     import _thread as thread

import pytz

import emdoor
from emdoor import TZ_INDIA, load_prompted_keys, add_prompted_key, remove_prompted_key, clear_prompted_keys
from amscan import *

from sqlalchemy import Column, Integer, String, ForeignKey, Table, create_engine
from sqlalchemy.orm import relationship, backref, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.expression import distinct, false, intersect_all, null, true
from sqlalchemy.sql.functions import concat, func, now, user
from sqlalchemy.sql.sqltypes import DATETIME, INTEGER, SMALLINT, DateTime, Time
from datetime import date, datetime

from typing import Optional, Iterable
from datetime import date, datetime
from apicalls import check_for_updates
from sqlalchemy import Column, Integer, String, ForeignKey, Table, create_engine, or_, and_, BINARY, func
from model import AMS_Event_Log, AMS_Keys, AMS_Access_Log, AMS_Event_Types, AMS_Activities, \
    AMS_Users, AMS_Cabinet, AMS_Site, AMS_Key_Pegs, \
    AMS_emergency_door_open, AMS_Activity_Progress_Status
from utils import show_msg_on_display, get_event_description

# try:
#     range, _print = xrange, print
#     def print(*args, **kwargs):
#         flush = kwargs.pop('flush', False)
#         _print(*args, **kwargs)
#         if flush:
#             kwargs.get('file', sys.stdout).flush()
# except NameError:
#     pass

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
EVENT_PEG_REG_DONE = 15
EVENT_PEG_REG_FAILED = 16
EVENT_CARD_REG_DONE = 17
EVENT_CARD_REG_FAILED = 18
EVENT_KEY_OVERDUE_RETURNED = 31
EVENT_BIO_REG_DONE = 32
EVENT_BIO_REG_FAILED = 33


EVENT_TYPE_EVENT = 3
EVENT_TYPE_ALARM = 1
EVENT_TYPE_EXCEPTION = 2

SLOT_STATUS_KEY_NOT_PRESENT = 0
SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT = 1
SLOT_STATUS_KEY_PRESENT_WRONG_SLOT = 2

BATTERY_CHARGE_PC = None

MAIN_DOOR_LOCK = 0
MAIN_DOOR_UN_LOCK = 1

tz_IN = pytz.timezone('Asia/Kolkata')


#KEY_DICT = {"2": 1, "5": 2, "8": 3, "3": 4, "6": 5, "9": 6, "4": 7, "7": 8, "10": 9, "108": 0, "103": "F1", "479": "F2"\
#            , "28": ".", "465": "UP", "11": "DN", "55": "ENTER"}
KEY_DICT = {"2": 1, "5": 2, "8": 3, "3": 4, "6": 5, "9": 6, "4": 7, "7": 8, "10": 9, "108": 0, "103": "F1", "479": "F2"\
            , "28": ".", "465": "UP", "11": "DN", "55": "ENTER"}

auth_mode = None 

def get_auth_mode():
    global auth_mode
    return auth_mode

def set_auth_mode(mode):
    global auth_mode
    auth_mode = mode

def get_login_type():
    mode = get_auth_mode()
    if mode == AUTH_MODE_PIN:
        return "PIN"
    elif mode == AUTH_MODE_CARD_PIN:
        return "CARD+PIN"
    elif mode == AUTH_MODE_BIO:
        return "BIO"
    return "PIN"  # default fallback



def get_key_interactions(ams_can2, session, cabinet, ams_access_log, user_auth, lib_display, lib_Buzzer, keys_taken_list, keys_returned_list):
    key_record = None
    lib_display.displayInit()
    if ams_can2.key_taken_event:
        print("############   Key has been taken out  ###########")
        
        for key in cabinet.keys:
            if key.peg_id == ams_can2.key_taken_id:
                key_record = key
                break

        if key_record:
            keys_msg_print = ("Key taken: " + (key_record.keyName.ljust(4, ' '))).encode('utf-8')
            print(keys_msg_print)
            ams_access_log.keysTaken = str(key_record.id)
            session.commit()
            print("key taken peg id is : ", end='')
            session.query(AMS_Keys).filter(
                AMS_Keys.peg_id == ams_can2.key_taken_id).update(
                {'keyTakenBy': user_auth["id"],
                    'keyTakenByUser': user_auth["name"],
                    'current_pos_strip_id': ams_can2.key_taken_position_list,
                    'current_pos_slot_no': ams_can2.key_taken_position_slot,
                    'keyTakenAtTime': datetime.now(tz_IN),
                    'keyStatus': SLOT_STATUS_KEY_NOT_PRESENT})
            session.commit()

            ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=key_record.id,
                                            activityId=None,
                                            eventId=EVENT_KEY_TAKEN_CORRECT,
                                            loginType=get_login_type(),
                                            access_log_id=ams_access_log.id,
                                            timeStamp=datetime.now(tz_IN),
                                            event_type=EVENT_TYPE_EVENT, is_posted=0)
            session.add(ams_event_log)
            session.commit()

            if key_record.keyName not in keys_taken_list:
                keys_taken_list.append(key_record.keyName)
                # add_prompted_key(key_record.keyName)
                # PROMPTED_KEYS.add(key_record.keyName)
        else:
            print("Key taken but key record not found for updating taken event")
            keys_msg_print = ("Key not reg.    ".encode('utf-8'))

        lib_display.displayClear()
        lib_display.displayString(keys_msg_print, 2)
        
        print("key taken out successfully....")
        ams_can2.key_taken_event = False
    
    elif ams_can2.key_inserted_event:
        print("############   key has been inserted  ###########")
        print("\n\nKEY INSERTED\n\n")
        for key in cabinet.keys:
            if key.peg_id == ams_can2.key_inserted_id:
                key_record = key

        # print(key_record.keyStrip, ams_can2.key_inserted_position_list, ams_can2.key_inserted_position_slot)
        if key_record:
            if key_record.keyStrip == ams_can2.key_inserted_position_list and \
                    key_record.keyPosition == ams_can2.key_inserted_position_slot:
                ams_can2.set_single_LED_state(ams_can2.key_inserted_position_list,
                                                ams_can2.key_inserted_position_slot,
                                                CAN_LED_STATE_OFF)
                keys_msg_print = ("Key return:" + (
                    key_record.keyName.ljust(4, ' '))).encode('utf-8')
                ams_access_log.keysReturned = str(key_record.id)
                session.commit()

                session.query(AMS_Keys).filter(
                    AMS_Keys.peg_id == ams_can2.key_inserted_id).update(
                    {'current_pos_door_id': 1,
                        'keyTakenBy': None,
                        'keyTakenAtTime': None,
                        'current_pos_strip_id': ams_can2.key_inserted_position_list,
                        'current_pos_slot_no': ams_can2.key_inserted_position_slot,
                        'keyStatus': SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT})
                session.commit()

                ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=key_record.id,
                                                activityId=None,
                                                eventId=EVENT_KEY_RETURNED_RIGHT_SLOT,
                                                loginType=get_login_type(),
                                                access_log_id=ams_access_log.id,
                                                timeStamp=datetime.now(tz_IN),
                                                event_type=EVENT_TYPE_EVENT, is_posted=0)
                session.add(ams_event_log)
                session.commit()

                # Log overdue key returned if applicable
                overdue_logged = session.query(AMS_Event_Log).filter_by(
                    keyId=key_record.id,
                    eventId=19  # EVENT_KEY_OVERDUE
                ).order_by(AMS_Event_Log.id.desc()).first()
                overdue_return_logged = session.query(AMS_Event_Log).filter_by(
                    keyId=key_record.id,
                    eventId=EVENT_KEY_OVERDUE_RETURNED 
                ).order_by(AMS_Event_Log.id.desc()).first()
                if overdue_logged and not overdue_return_logged:
                    try:
                        ams_event_log = AMS_Event_Log(
                            userId=user_auth["id"],
                            keyId=key_record.id,
                            activityId=None,
                            eventId=EVENT_KEY_OVERDUE_RETURNED,  # EVENT_KEY_OVERDUE_RETURNED
                            loginType=get_login_type(),
                            access_log_id=ams_access_log.id,
                            timeStamp=datetime.now(tz_IN),
                            event_type=EVENT_TYPE_EXCEPTION,
                            is_posted=0,
                        )
                        session.add(ams_event_log)
                        session.commit()
                    except Exception as e:
                        print(f"Exception while logging overdue key return: {e}")
                lib_display.displayClear()
                lib_display.displayString(keys_msg_print, 2)
                ams_can2.key_inserted_event = False
                if key_record.keyName not in keys_returned_list:
                    keys_returned_list.append(key_record.keyName)
                    if key_record.keyName in load_prompted_keys():   # <-- REMOVE when returned
                        remove_prompted_key(key_record.keyName)
                        # PROMPTED_KEYS.remove(key_record.keyName)

            elif key_record.keyStrip != ams_can2.key_inserted_position_list or \
                key_record.keyPosition != ams_can2.key_inserted_position_slot:
                ams_can2.set_single_LED_state(ams_can2.key_inserted_position_list,
                                                ams_can2.key_inserted_position_slot,
                                                CAN_LED_STATE_BLINK)
                keys_msg_print = ("Key return:" + (
                    key_record.keyName.ljust(4, ' '))).encode('utf-8')

                print("in wrong condition ", end='')
                print(keys_msg_print)

                ams_access_log.keysReturned = str(key_record.id)
                session.commit()

                session.query(AMS_Keys).filter(
                    AMS_Keys.peg_id == ams_can2.key_inserted_id).update(
                    {'current_pos_door_id': 1,
                        'current_pos_strip_id': ams_can2.key_inserted_position_list,
                        'current_pos_slot_no': ams_can2.key_inserted_position_slot,
                        'keyStatus': SLOT_STATUS_KEY_PRESENT_WRONG_SLOT})
                session.commit()

                # is_posted added by ravi
                ams_event_log = AMS_Event_Log(userId=user_auth["id"],
                                                keyId=key_record.id,
                                                activityId=None,
                                                eventId=EVENT_KEY_RETURNED_WRONG_SLOT,
                                                loginType=get_login_type(),
                                                access_log_id=ams_access_log.id,
                                                timeStamp=datetime.now(tz_IN),
                                                event_type=EVENT_TYPE_ALARM, is_posted=0)
                session.add(ams_event_log)
                session.commit()
                lib_display.displayClear()
                lib_display.displayString(keys_msg_print, 2)
                
                ams_can2.key_inserted_event = False
                IS_KEY_IN_WRONG_SLOT = True

                if not ams_can2.get_key_id(key_record.keyStrip,
                                            key_record.keyPosition):
                    ams_can2.set_single_key_lock_state(ams_can2.key_inserted_position_list,
                                                        ams_can2.key_inserted_position_slot,
                                                        CAN_KEY_UNLOCKED)
                    ams_can2.set_single_LED_state(ams_can2.key_inserted_position_list,
                                                    ams_can2.key_inserted_position_slot,
                                                    CAN_LED_STATE_BLINK)
                    ams_can2.set_single_key_lock_state(key_record.keyStrip,
                                                        key_record.keyPosition,
                                                        CAN_KEY_UNLOCKED)
                    ams_can2.set_single_LED_state(key_record.keyStrip,
                                                    key_record.keyPosition,
                                                    CAN_LED_STATE_ON)

                    correct_key_POS = (key_record.keyPosition + ((key_record.keyStrip-1)*14))
                    current_key_POS = (ams_can2.key_inserted_position_slot + (
                                (ams_can2.key_inserted_position_list - 1) * 14))
                    msg_line1 = ("Wrong slot  " + str(current_key_POS) + "  ").encode('utf-8')
                    msg_line2 = ("Put in slot " + str(correct_key_POS) + "  ").encode('utf-8')
                    lib_display.displayString(msg_line1, 1)
                    lib_display.displayString(msg_line2, 2)
                    
                    if key_record.id not in keys_returned_list:
                        keys_returned_list.append(key_record.id)
                    if key_record.id in keys_taken_list:
                        keys_taken_list.remove(key_record.id)
                else:
                    msg_line1 = "Key in wrong pos".encode('utf-8')
                    msg_line2 = "Correct pos n/a ".encode('utf-8')
                    lib_display.displayClear()
                    lib_display.displayString(msg_line1, 1)
                    lib_display.displayString(msg_line2, 2)
                    
                IS_KEY_IN_WRONG_SLOT_Correct_Strip = key_record.keyStrip
                IS_KEY_IN_WRONG_SLOT_Correct_Pos = key_record.keyPosition
                IS_KEY_IN_WRONG_SLOT_Wrong_Strip =  ams_can2.key_inserted_position_slot
                IS_KEY_IN_WRONG_SLOT_Wrong_Pos = ams_can2.key_inserted_position_list
                IS_KEY_IN_WRONG_SLOT_User_PIN = None
                lib_Buzzer.setBuzzerOn()
                sleep(5)
                lib_Buzzer.setBuzzerOff()
                if key_record.keyName not in keys_returned_list:
                    keys_returned_list.append(key_record.keyName)

        else:
            print("Key inserted but key record not found for updating inserted event")
            msg_line1 = "Key record n/a  ".encode('utf-8')
            msg_line2 = "Register the key".encode('utf-8')
            lib_display.displayClear()
            lib_display.displayString(msg_line1, 1)
            lib_display.displayString(msg_line2, 2)
            sleep(1)

def select_key(session, lib_display, lib_keypad, FD_KEYPAD):
    keys = session.query(AMS_Keys).all()
    key_names = map(lambda x:x.keyName, keys)
    print(key_names)

    class Key:
        def __init__(self, key_name = None, next = None, prev = None):
            self.key_name = key_name
            self.next = next
            self.prev = prev

    class KeyDoublyLinkedList:

        def __init__(self):
            self.head = Key()

        def append(self, name):
            new_key = Key(key_name=name)
            if self.head.key_name is None:
                self.head = new_key
                self.head.prev = new_key
                self.head.next = new_key
                return
            current_key = self.head
            while current_key.next != self.head:
                current_key = current_key.next
            new_key.next = self.head
            current_key.next = new_key
            new_key.prev = current_key
            self.head.prev = new_key

        def print_list(self):
            elements = []
            current_key = self.head
            while current_key:
                elements.append(current_key.key_name)
                current_key = current_key.next
                if current_key == self.head:
                    break
            return elements

        def length(self):
            current_key = self.head
            count = 0
            while current_key:
                count += 1
                current_key = current_key.next
                if current_key == self.head:
                    break
            return count

    def print_on_display(header):
        lib_display.displayClear()
        sleep(0.2)
        current_head = header
        for i in range(2):
            if current_head:
                # print(f'key: {current_head.key_name}')
                lib_display.displayString(current_head.key_name.encode('utf-8'), i+1)
                current_head = current_head.next

    def select_particular_key(key_names):
        my_list = KeyDoublyLinkedList()

        keys = key_names

        for key in keys:
            my_list.append(key)
        print(f"there are all {my_list.length()} keys present in the cabinet")
        # print(my_list.print_list())

        selected_key = None
        header = my_list.head
        print_on_display(header)
        while True:
            print()
            key = lib_keypad.keypadHandler(FD_KEYPAD)
            in_data = str(KEY_DICT[str(key)])
            # up
            if in_data == "UP":
                print('up')
                if header.prev:
                    header = header.prev
                    print_on_display(header)
                else:
                    print_on_display(header)
            # down
            elif in_data == "DN":
                print('down')
                if header.next:
                    header = header.next
                    print_on_display(header)
                else:
                    print_on_display(header)
            # select this
            elif in_data == "ENTER":
                print('enetered')
                selected_key = header.key_name
                break
            # wrong input
            else:
                print('select proper input')
            

        print(f'*********** you have selected {selected_key} ************')

    select_particular_key(key_names)

##############################################

def key_str_4(session, user_auth, ams_access_log, lib_display, lib_keypad, FD_KEYPAD):
    if not user_auth or (isinstance(user_auth, dict) and "id" not in user_auth) or (not isinstance(user_auth, dict) and not hasattr(user_auth, "id")):
        show_msg_on_display(lib_display, msg1="User not found!", msg2="Operation cancelled", sleep_duration=2)
        return
    print("[DEBUG] user_auth:", user_auth)
    print("[DEBUG] ams_access_log:", ams_access_log)
    if ams_access_log is None:
        ams_access_log = AMS_Access_Log(
            signInTime=datetime.now(tz_IN),
            signInMode=get_auth_mode(),
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
            event_type_id=EVENT_TYPE_EVENT,
            is_posted=0
        )
        session.add(ams_access_log)
        session.commit()
    print("############   Step 23 - Date/Time Setting  ###########")
    current_datetime = datetime.now(tz_IN)
    current_date_str = current_datetime.strftime("%d-%m-%Y")
    current_time_str = current_datetime.strftime("%H:%M")
    show_msg_on_display(lib_display, msg1="Current Date:", msg2=current_date_str, sleep_duration=2)
    show_msg_on_display(lib_display, msg1="Current Time:", msg2=current_time_str, sleep_duration=2)
    show_msg_on_display(lib_display, msg1="Enter Date:", msg2="", sleep_duration=2)
    show_msg_on_display(lib_display, msg1="DDMMYYYY:", msg2="", sleep_duration=None)
    date_entered = ""
    while True:
        key = lib_keypad.keypadHandler(FD_KEYPAD)
        key_str = str(KEY_DICT[str(key)])
        if key is not None:
            if key_str.isnumeric():
                if len(date_entered) < 8:
                    date_entered += key_str
                    lib_display.displayStringWithPosition(date_entered.encode("utf-8"), 2, 0)
            elif key_str == "DN":  # CLEAR
                date_entered = ""
                lib_display.displayClear()
                lib_display.displayString("Enter Date:".encode("utf-8"), 1)
                lib_display.displayString("DDMMYYYY".encode("utf-8"), 2)
            elif key_str == "ENTER":
                if len(date_entered) == 8:
                    break
                else:
                    show_msg_on_display(lib_display, msg1="Invalid Date!", msg2="Try Again", sleep_duration=2)
                    date_entered = ""
                    lib_display.displayClear()
                    lib_display.displayString("Enter Date:".encode("utf-8"), 1)
                    lib_display.displayString("DDMMYYYY".encode("utf-8"), 2)
            elif key_str == "UP":  # HOME
                show_msg_on_display(lib_display, msg1="Returning to", msg2="Main Menu", sleep_duration=2)
                return
    try:
        if len(date_entered) == 8 and date_entered.isdigit():
            date_entered = f"{date_entered[:2]}-{date_entered[2:4]}-{date_entered[4:]}"
        day, month, year = date_entered.split("-")
        day = int(day)
        month = int(month)
        year = int(year)
        if not (1 <= day <= 31 and 1 <= month <= 12 and 2000 <= year <= 2099):
            show_msg_on_display(lib_display, msg1="Invalid Date!", msg2="Try Again", sleep_duration=2)
            return
    except ValueError:
        show_msg_on_display(lib_display, msg1="Invalid Date!", msg2="Try Again", sleep_duration=2)
        return
    show_msg_on_display(lib_display, msg1="Enter Time:", msg2="HHMM", sleep_duration=None)
    time_entered = ""
    while True:
        key = lib_keypad.keypadHandler(FD_KEYPAD)
        key_str = str(KEY_DICT[str(key)])
        if key is not None:
            if key_str.isnumeric():
                if len(time_entered) < 4:
                    time_entered += key_str
                    lib_display.displayStringWithPosition(time_entered.encode("utf-8"), 2, 0)
            elif key_str == "DN":  # CLEAR
                time_entered = ""
                lib_display.displayClear()
                lib_display.displayString("Enter Time:".encode("utf-8"), 1)
                lib_display.displayString("HHMM".encode("utf-8"), 2)
            elif key_str == "ENTER":
                if len(time_entered) == 4:
                    break
                else:
                    show_msg_on_display(lib_display, msg1="Invalid Time!", msg2="Try Again", sleep_duration=2)
                    time_entered = ""
                    lib_display.displayClear()
                    lib_display.displayString("Enter Time:".encode("utf-8"), 1)
                    lib_display.displayString("HHMM".encode("utf-8"), 2)
            elif key_str == "UP":  # HOME
                show_msg_on_display(lib_display, msg1="Returning to", msg2="Main Menu", sleep_duration=2)
                return
    try:
        if len(time_entered) == 4 and time_entered.isdigit():
            time_entered = f"{time_entered[:2]}:{time_entered[2:]}"
        hour, minute = time_entered.split(":")
        hour = int(hour)
        minute = int(minute)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            show_msg_on_display(lib_display, msg1="Invalid Time!", msg2="Try Again", sleep_duration=2)
            return
    except ValueError:
        show_msg_on_display(lib_display, msg1="Invalid Time!", msg2="Try Again", sleep_duration=2)
        return
    show_msg_on_display(lib_display, msg1="Confirm Settings:", msg2=f"Date: {date_entered}", sleep_duration=2)
    show_msg_on_display(lib_display, msg1="Time:", msg2=time_entered, sleep_duration=2)
    show_msg_on_display(lib_display, msg1="Press ENTER to  confirm", msg2="", sleep_duration=None)
    while True:
        key = lib_keypad.keypadHandler(FD_KEYPAD)
        key_str = str(KEY_DICT[str(key)])
        if key_str == "ENTER":
            break
        elif key_str == "UP":  # HOME
            show_msg_on_display(lib_display, msg1="Cancelled!", msg2="Returning to Menu", sleep_duration=2)
            return
    try:
        system_date = f"{year:04d}-{month:02d}-{day:02d}"
        system_time = f"{hour:02d}:{minute:02d}:00"
        # Set both date and time together
        subprocess.run(["date", "-s", f"{system_date} {system_time}"], capture_output=True, text=True)
        subprocess.run(["hwclock", "--systohc"], capture_output=True, text=True)

        show_msg_on_display(lib_display, msg1="Date/Time Set!", msg2="Success", sleep_duration=2)

        ams_event_log = AMS_Event_Log(
            userId=user_auth["id"],
            keyId=None,
            activityId=None,
            eventId=DATE_SET,
            loginType="PIN",
            access_log_id=ams_access_log.id,
            timeStamp=datetime.now(tz_IN),
            event_type=EVENT_TYPE_EVENT,
            is_posted=0)
        session.add(ams_event_log)
        session.commit()
        
        new_datetime = datetime.now(tz_IN)
        new_date_str = new_datetime.strftime("%d-%m-%Y")
        new_time_str = new_datetime.strftime("%H:%M")
        show_msg_on_display(lib_display, msg1="New Date:", msg2=new_date_str, sleep_duration=2)
        show_msg_on_display(lib_display, msg1="New Time:", msg2=new_time_str, sleep_duration=2)
        print(f"############   Date/Time successfully set to {date_entered} {time_entered}  ###########")
        return
    except Exception as e:
        print(f"Error setting date/time: {e}")
        show_msg_on_display(lib_display, msg1="Setting Failed!", msg2="Try Again", sleep_duration=3)
        return


def key_str_5(session, user_auth, ams_access_log, lib_display, lib_keypad, FD_KEYPAD):
    if not user_auth or (isinstance(user_auth, dict) and "id" not in user_auth) or (not isinstance(user_auth, dict) and not hasattr(user_auth, "id")):
        show_msg_on_display(lib_display, msg1="User not found!", msg2="Operation cancelled", sleep_duration=2)
        return
    print("[DEBUG] user_auth:", user_auth)
    print("[DEBUG] ams_access_log:", ams_access_log)
    if ams_access_log is None:
        ams_access_log = AMS_Access_Log(
            signInTime=datetime.now(tz_IN),
            signInMode=get_auth_mode(),
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
            event_type_id=EVENT_TYPE_EVENT,
            is_posted=0
        )
        session.add(ams_access_log)
        session.commit()
    ams_event_log = AMS_Event_Log(
        userId=user_auth["id"],
        keyId=None,
        activityId=None,
        eventId=EVENT_IP_ADDRESS_CHANGE_INITIALISED,
        loginType=get_login_type(),
        access_log_id=ams_access_log.id,
        timeStamp=datetime.now(tz_IN),
        event_type=EVENT_TYPE_EVENT,
        is_posted=0
    )
    session.add(ams_event_log)
    session.commit()
    change_ip_address_gateway(session, user_auth, ams_access_log, lib_display, lib_keypad, FD_KEYPAD)

def quit_function(fn_name):
    # print to stderr, unbuffered in Python 2.
    print('\n\tTIMEOUT!!! Press any key', file=sys.stderr)
    #sys.stderr.flush()
    thread.interrupt_main() # raises KeyboardInterrupt


def exit_after(s):
    '''
    use as decorator to exit process if 
    function takes longer than s seconds
    '''
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



@exit_after(60)
def login_using_PIN(lib_display, lib_keypad, FD_KEYPAD):
    pin_char_count = 0
    pin_entered = ''
    while pin_char_count < 5:
        key = lib_keypad.keypadHandler(FD_KEYPAD)
        key_str = str(KEY_DICT[str(key)])
        if key is not None:
            if key_str.isnumeric():
                pin_entered = pin_entered + key_str
                lib_display.displayStringWithPosition("*".encode('utf-8'), 2, 10 + pin_char_count)
                pin_char_count += 1
            elif key_str == "ENTER":
                return pin_entered
            elif key_str == "DN":  # CLEAR
                pin_entered = ""
                pin_char_count = 0
                lib_display.displayClear()
                lib_display.displayString("Enter PIN:".encode('utf-8'), 2)
            elif key_str == "UP":  # HOME
                return None
    return pin_entered


def validate_fingerprint_user(session, scanned_template_path="user_template", reference_file_path="reference_file"):
    recordset = session.query(AMS_Users).all()
    if not recordset:
        return None

    for user in recordset:
        if user.fpTemplate is None:
            continue

        # Save stored template to reference file
        with open(reference_file_path, 'wb') as f:
            f.write(user.fpTemplate)

        # Run identification
        stdout = subprocess.run(
            ["/home/ams-core/FCIdentifyFingerCPP", scanned_template_path, reference_file_path],
            capture_output=True,
            text=True
        ).stdout

        int_score = None
        for line in stdout.splitlines():
            # print("FCIdentifyFingerCPP >>", line)
            if "Identification score:" in line:
                str_score = (line[21:]).strip()
                if str_score.isnumeric():
                    int_score = int(str_score)

        # If score is valid and above threshold
        if int_score and int_score > 96:
            return user, int_score

    return None


@exit_after(60)
def login_using_PIN_Card_Bio(lib_display, lib_keypad, FD_KEYPAD, session):
    pin_char_count = 0
    pin_entered = ''
    Card_No = 0
    login_option = ""
    login_option_str = ""
    # Wait for biometric scan or Card swipe

    lib_display.displayClear()
    # after msg first number is for row and second is for column {default: 0}
    lib_display.displayString("Press 1 for Card".encode('utf-8'), 1)
    lib_display.displayString("Press 2 for Bio.".encode('utf-8'), 2)

    login_option = lib_keypad.keypadHandler(FD_KEYPAD)
    login_option_str = str(KEY_DICT[str(login_option)])
    if login_option_str == '1':
        lib_display.displayClear()
        lib_display.displayString("Show your card  ".encode('utf-8'), 1)
        timer_sec = 0
        while True:
            timer_sec += 1
            sleep(0.25)
            Card_No = amsbms.cardNo
            if int(Card_No) > 0 or timer_sec > 60:
                break
        if int(Card_No) > 0:
            lib_display.displayString("                ".encode('utf-8'), 1)
            lib_display.displayString("Enter PIN: ".encode('utf-8'), 2)
            pin_char_count = 0
            pin_entered = ''
            while pin_char_count < 5:
                key = lib_keypad.keypadHandler(FD_KEYPAD)
                key_str = str(KEY_DICT[str(key)])
                if key_str.isnumeric():
                    pin_entered = pin_entered + key_str
                    lib_display.displayStringWithPosition("*".encode('utf-8'), 2, 10 + pin_char_count)
                    pin_char_count += 1
                elif key_str == "ENTER":
                    set_auth_mode(AUTH_MODE_CARD_PIN)
                    return AUTH_MODE_CARD_PIN, pin_entered, str(Card_No)
                elif key_str == "F1":
                    set_auth_mode(AUTH_MODE_CARD_PIN)
                    return AUTH_MODE_CARD_PIN, "", str(Card_No)
                elif key_str == "DN":  # CLEAR
                    pin_entered = ""
                    pin_char_count = 0
                    lib_display.displayClear()
                    lib_display.displayString("Enter PIN:".encode('utf-8'), 2)
                elif key_str == "UP":  # HOME
                    return None, None, None
            set_auth_mode(AUTH_MODE_CARD_PIN)
            return AUTH_MODE_CARD_PIN, pin_entered, str(Card_No)
        else:
            lib_display.displayString(" TIMEOUT!!! ".encode('utf-8'), 1)
            sleep(2)
            set_auth_mode(AUTH_MODE_CARD_PIN)
            return AUTH_MODE_CARD_PIN, 0, ""
    elif login_option_str == '2':
        lib_display.displayClear()
        lib_display.displayString("Scan finger now ".encode('utf-8'), 1)
        if os.path.exists("frame_Ex.bmp"):
            os.remove("frame_Ex.bmp")
        if os.path.exists("user_template"):
            os.remove("user_template")

        return_val = subprocess.run("/home/ams-core/ftrScanAPI_Ex")
        lib_display.displayString("".encode('utf-8'), 1)
        lib_display.displayString("Scan ok pls wait".encode('utf-8'), 2)
        enroll_data = subprocess.run(
            ["/home/ams-core/FCEnrollFingerFromImageCPP", "frame_Ex.bmp", "user_template"],
            capture_output=True,
            text=True
        )

        match = validate_fingerprint_user(session)

        if match:
            user, score = match
            pin_entered = user.pinCode
            set_auth_mode(AUTH_MODE_BIO)
            return AUTH_MODE_BIO, pin_entered, user.cardNo
        else:
            set_auth_mode(AUTH_MODE_BIO)
            return AUTH_MODE_BIO, "", 0
    elif login_option_str == "DN":  # CLEAR
        return None, None, None
    elif login_option_str == "UP":  # HOME
        return None, None, None
    else:
        return 0, "", 0

@exit_after(60)
def get_activity_code(lib_display, lib_keypad, FD_KEYPAD):
    act_char_count = 0
    act_code_entered = ''
    while act_char_count < 2:
        key = lib_keypad.keypadHandler(FD_KEYPAD)
        key_str = str(KEY_DICT[str(key)])
        if key is not None:
            if key_str.isnumeric():
                act_code_entered = act_code_entered + key_str
                lib_display.displayStringWithPosition("*".encode('utf-8'), 2, 14 + act_char_count)
                act_char_count += 1
            elif key_str == "ENTER":
                return act_code_entered
            elif key_str == "DN":  # CLEAR
                act_code_entered = ""
                act_char_count = 0
                lib_display.displayClear()
                lib_display.displayString("Task Code:".encode("utf-8"), 1)
            elif key_str == "UP":  # HOME
                return None
    return act_code_entered


    while True:
        code = int(input("Enter activity code:"))
        if not code:
            #print("Pls enter valid 2 digit activity code")
            continue
        else:
            return code


# @exit_after(30)
# def get_user_login_option(lib_keypad, FD_KEYPAD):
#     key_str = ''
#     print("inside get_user_login_option")
#     key = lib_keypad.keypadHandler(FD_KEYPAD)
#     key_str = str(KEY_DICT[str(key)])
#     return key_str

def ams_header_line(session):
    ams_alarm_count = session.query(AMS_Event_Log).filter(AMS_Event_Log.event_type != 3).count()
    #print("Alarm Count = " + str(ams_alarm_count))
    bcp = amsbms.batteryPc
    ams_header_line_str = "Alarm " + str(ams_alarm_count) + " Bat" + str(bcp) + "%"
    return ams_header_line_str


def update_keys_status(ams_can, list_ID, session):

    # for key_num in range(1, 15):
    #     key_id = ams_can.get_key_id(list_ID, key_num)
    #     if key_id:
    #         print("Key number:"+ str(key_num))
    #         session.query(AMS_Keys).filter(AMS_Keys.peg_id == key_id).update({'current_pos_strip_id': list_ID,
    #                                                                           'current_pos_slot_no': key_num,
    #                                                                           'keyStatus':SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT})
    #         session.commit()
    #         session.query(AMS_Keys).filter(AMS_Keys.peg_id == key_id).filter(
    #             (AMS_Keys.keyStrip == list_ID) & (AMS_Keys.current_pos_slot_no == (key_num))).update(
    #             {'keyStatus': SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT})
    #         session.commit()
    #         session.query(AMS_Keys).filter(AMS_Keys.peg_id == key_id).filter(
    #             (AMS_Keys.keyStrip != list_ID) | (AMS_Keys.current_pos_slot_no != (key_num))).update(
    #             {'keyStatus': SLOT_STATUS_KEY_PRESENT_WRONG_SLOT})
    #         session.commit()
    #     else:
    #         session.query(AMS_Keys).filter(AMS_Keys.current_pos_strip_id == list_ID)\
    #             .filter(AMS_Keys.current_pos_slot_no == (key_num))\
    #             .update({'keyStatus': SLOT_STATUS_KEY_NOT_PRESENT})
    #         session.commit()
    #
    for key_num in range(1, 15):
        key_id = ams_can.get_key_id(list_ID, key_num)
        if key_id:
            current_key = (
                session.query(AMS_Keys).filter(AMS_Keys.peg_id == key_id).first()
            )
            if current_key:
                if (
                    current_key.current_pos_slot_no == current_key.keyPosition
                    and current_key.current_pos_strip_id == current_key.keyStrip
                    #and current_key.is_critical == 1
                ):
                    #current_key.color = "Blue"
                    current_key.keyStatus = SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT
                if (
                    current_key.current_pos_slot_no == current_key.keyPosition
                    and current_key.current_pos_strip_id == current_key.keyStrip
                    #and current_key.is_critical == 0
                ):
                    #current_key.color = "Green"
                    current_key.keyStatus = SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT
                if (
                    current_key.current_pos_slot_no != current_key.keyPosition
                    or current_key.current_pos_strip_id != current_key.keyStrip
                ):
                    #current_key.color = "Black"
                    current_key.keyStatus = SLOT_STATUS_KEY_PRESENT_WRONG_SLOT
                session.commit()
            else:
                return
        else:
            session.query(AMS_Keys).filter(
                AMS_Keys.current_pos_strip_id == list_ID
            ).filter(AMS_Keys.current_pos_slot_no == (key_num)).update(
                {"keyStatus": SLOT_STATUS_KEY_NOT_PRESENT}
            )
            session.commit()

def alarm_for_previous_keys(session, lib_display, lib_Buzzer):
    try:
        current_time = datetime.now(TZ_INDIA)
        keys_taken = session.query(AMS_Keys).filter(AMS_Keys.keyStatus == 0).all()
        prompted__keys = load_prompted_keys()
        print(f"Keys taken: {[key.keyName for key in keys_taken]}")
        print(f"Prompted Keys list: {prompted__keys}")

        for key in keys_taken:
            print(f"Checking {key.keyName} against PROMPTED_KEYS: {prompted__keys}, key in prompted__keys: {key} , {key in prompted__keys}  ")
            if key.keyName in prompted__keys:
                if not key.keyTakenAtTime:
                    event = (
                        session.query(AMS_Event_Log)
                        .filter(AMS_Event_Log.keyId == key.id)
                        .order_by(AMS_Event_Log.id.desc())
                        .first()
                    )
                    if event and event.eventId != 9:
                        continue
                    if event and event.timeStamp:
                        taken_time = event.timeStamp
                    else:
                        taken_time = current_time
                else:
                    taken_time = key.keyTakenAtTime

                taken_time = taken_time.astimezone(TZ_INDIA)
                

                lib_display.displayClear()
                lib_display.displayString(f'Key Out: {key.keyName}'.encode("utf-8"), 1)
                minutes_out = int((current_time - taken_time).total_seconds() // 60)
                lib_display.displayString(f'Time: {minutes_out} min'.encode("utf-8"), 2)
                
                lib_Buzzer.setBuzzerOn()
                print(f"Buzzer ON for overdue key: {key.keyName}")
                # sleep(10)
                sleep(2)
                lib_Buzzer.setBuzzerOff()
                
                key_obj = session.query(AMS_Keys).filter(AMS_Keys.keyName == key.keyName).first()
                if key_obj:
                    access_log = session.query(AMS_Access_Log)\
                        .filter(AMS_Access_Log.keysTaken.like(f"%{key_obj.id}%"))\
                        .order_by(AMS_Access_Log.id.desc())\
                        .first()

                    ams_event_log = AMS_Event_Log(
                        userId=int(key_obj.keyTakenBy) if key_obj.keyTakenBy else None,
                        keyId=key_obj.id,
                        activityId=access_log.activityCode if access_log else None,
                        eventId= 19, #EVENT_KEY_OVERDUE,
                        loginType="",
                        access_log_id=access_log.id if access_log else None,
                        timeStamp=current_time,
                        event_type=EVENT_TYPE_EXCEPTION,
                        is_posted=0,
                    )
                    session.add(ams_event_log)
                    session.commit()
    except Exception as ex:
        print(ex)




def main():

    # Set TIMEZONE
    tz_IN = pytz.timezone('Asia/Kolkata')
    IS_KEY_IN_WRONG_SLOT = None
    IS_KEY_IN_WRONG_SLOT_Correct_Strip = None
    IS_KEY_IN_WRONG_SLOT_Correct_Pos = None
    IS_KEY_IN_WRONG_SLOT_Wrong_Strip = None
    IS_KEY_IN_WRONG_SLOT_Wrong_Pos = None
    IS_KEY_IN_WRONG_SLOT_User_PIN = None
    IS_KEY_IN_WRONG_SLOT_Message = None
    # Initialize hardware peripherals
    # Initialize 16x2 LCD DISPLAY
    lib_display = ctypes.CDLL("libDisplay.so")
    lib_display.displayDefaultLoginMessage.argtypes = []
    lib_display.displayStringWithPosition.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
    lib_display.displayString.argtypes = [ctypes.c_char_p, ctypes.c_int]
    lib_display.displayClear.argtypes = []
    lib_display.displayInit.argtypes = []
    lib_display.displayClose.argtypes = []

    lib_Buzzer = ctypes.CDLL("libBuzzer.so")
    lib_Buzzer.setBuzzerOn.argtypes = []
    lib_Buzzer.setBuzzerOff.argtypes = []

    BATTERY_CHARGE_PC = amsbms.batteryPc

    # Initialize KEY-PAD
    lib_keypad = ctypes.CDLL("libKeypad.so")
    lib_keypad.keypadInit.argtypes = []
    lib_keypad.keypadHandler.argtypes = [ctypes.c_int]
    lib_keypad.keypadClose.argtypes = [ctypes.c_int]
    FD_KEYPAD = lib_keypad.keypadInit()

    # initializing engine/connection and session to handle CRUD operations
    engine = create_engine('sqlite:////home/ams-core/csiams.dev.sqlite')
    Session = sessionmaker()
    Session.configure(bind=engine)
    session = Session()

    # Clear screen and display welcome message
    lib_display.displayInit()
    lib_display.displayClear()

    # print("Testing keypad and display...")
    #
    # timesec = 0
    # disp_str = ''
    #
    # while timesec < 16:
    #     key = lib_keypad.keypadHandler(FD_KEYPAD)
    #     key_str = str(KEY_DICT[str(key)])
    #     if key_str:
    #         lib_display.displayString(key_str.encode('utf-8'), 1)
    #         print("\nKey code : " + str(key))
    #     timesec += 1
    #
    # print("Display and keypad testing done")

    # checking for cabinet version update

    
    # try:
    #     check_for_updates(session=session, lib_display=lib_display)
    # except Exception as e:
    #     print(e)


    # under testing
    # select_key(session, lib_display, lib_keypad, FD_KEYPAD)

    ams_cabinet = AMS_Cabinet()

    ams_event_types = AMS_Event_Types()
    ams_access_log = None
    ams_event_log = None
    ams_user = AMS_Users()
    ams_can = None
    ams_alarm_count = 0

    cabinet = session.query(AMS_Cabinet).one_or_none()
    current_date = datetime.now(tz_IN).strftime('%d-%m-%Y %H:%M')
    if cabinet:

        sleep(2)
        current_date = datetime.now(tz_IN).strftime('%d-%m-%Y %H:%M')
        lib_display.displayString("WELCOME AMS V1.2".encode('utf-8'), 1)
        lib_display.displayString(current_date.encode('utf-8'), 2)
        sleep(2)
        # Display Battery Charge %
        BATTERY_CHARGE_PC = amsbms.batteryPc
        battery_pc_msg = "Battery Chrg:" + str(BATTERY_CHARGE_PC) + "%"
        lib_display.displayString(battery_pc_msg.encode('utf-8'), 2)
        sleep(2)

        # lib_display.displayString("Please wait...  ".encode('utf-8'), 2)
        ams_can = AMS_CAN()
        strip_version = ams_can.get_version_number(1)
        strip_version = ams_can.get_version_number(2)
        sleep(2)

        lib_KeyboxLock = ctypes.CDLL("libKeyboxLock.so")
        lib_KeyboxLock.getDoorSensorStatus1.argtypes = []
        lib_KeyboxLock.setKeyBoxLock.argtypes = [ctypes.c_int]
        lib_KeyboxLock.getDoorSensorStatus1.argtypes = []

        ams_can = AMS_CAN()
        sleep(6)
        strip_version = ams_can.get_version_number(1)
        strip_version = ams_can.get_version_number(2)
        ams_event_logs = AMS_Event_Log()
        print("\nNo of key-lists : " + str(len(ams_can.key_lists)))
        for keys in ams_can.key_lists:
            print("Key-list Id : " + str(keys))

        lib_display.displayString("WELCOME AMS V1.2".encode('utf-8'), 1)
        lib_display.displayString(current_date.encode('utf-8'), 2)

        for keylistid in ams_can.key_lists:
            ams_can.unlock_all_positions(keylistid)
            ams_can.set_all_LED_OFF(keylistid)
        # print("\n** 1")
        pegs_verified = False


        # code by ravi
        is_activity = session.query(AMS_Activity_Progress_Status).filter(AMS_Activity_Progress_Status.id == 1).one_or_none()
        # pending_acts = dict()
        # code by ravi


        while True:
            #print("############   Step 1  ###########")
            try:
                print("\n** 2")
                print(cabinet.site)

                header_line = ams_header_line(session)
                lib_display.displayInit()
                lib_display.displayClear()
                lib_display.displayString(header_line.encode('utf-8'), 1)
                login_msg = "Site: " + cabinet.site.siteName + (' ' * int(10 - len(cabinet.site.siteName)))
                sleep(1)
                # if not pegs_verified:
                lib_display.displayString("Please wait...  ".encode('utf-8'), 2)
                for lists in ams_can.key_lists:
                    update_keys_status(ams_can, lists, session)
                pegs_verified = True

                lib_display.displayString(login_msg.encode('utf-8'), 2)


# --------------------------------------------------------------------------------------------------------------



                # Wait for user to press ENTER for login, or FUNCTION KEYS for additional option
                # key_str = ''
                # ams_emergency_req = AMS_emergency_door_open()
                # print("\n** 3")
                # while key_str == '':
                #     try:
                #         key_str = get_user_login_option(lib_keypad, FD_KEYPAD)
                #         print("\n** 4")
                #         if key_str != '':
                #             rec_emg = ams_emergency_req.is_emergency_req_received(session)
                #             print("\n** 5")
                #             print(f'rec_emg {rec_emg}')
                #             # Check for other house-keeping activities
                #             if rec_emg:
                #                 print("\n** 6")
                #                 lib_display.displayClear()
                #                 lib_display.displayString("Emergency req. ".encode('utf-8'), 1)
                #                 lib_display.displayString("Opening door ".encode('utf-8'), 2)
                #                 ams_can.lib_door_lock.setKeyBoxLock(ams_can.Lock_FD, 1, 1, 1)
                #                 ams_can.unlock_all_positions(1)
                #                 ams_can.set_all_LED_ON(1, False)
                #                 ams_can.unlock_all_positions(2)
                #                 ams_can.set_all_LED_ON(2, False)
                #                 ams_can.door_closed_status = False
                #                 # Save to DB
                #                 print(datetime.now(tz_IN))
                #                 ams_access_log.doorOpenTime = datetime.now(tz_IN)
                #                 ams_access_log.event_type_id = EVENT_TYPE_ALARM
                #                 ams_access_log.signInUserId = rec_emg.userId
                #                 session.commit()

                #                 # is_posted added by ravi
                #                 ams_event_log = AMS_Event_Log(userId=rec_emg.userId, keyId=None,
                #                                               activityId=None,
                #                                               eventId=EVENT_EMERGENCY_DOOR_OPEN,
                #                                               loginType="WEB",
                #                                               access_log_id=ams_access_log.id,
                #                                               timeStamp=datetime.now(tz_IN),
                #                                               event_type=EVENT_TYPE_ALARM, is_posted=0)
                #                 session.add(ams_event_log)
                #                 session.commit()
            
                #                 sec_counter = 0
                #                 door_is_open = True
                #                 while door_is_open:
                #                     print("\n** 7")
                #                     door_status = lib_KeyboxLock.getDoorSensorStatus1()
                #                     sleep(1)
                #                     sec_counter += 1
                #                     if door_status == 0:
                #                         door_is_open = True
                #                     elif door_status == 1:
                #                         door_is_open = False
                #                         break
                                    
                #                     # code by ravi
                #                     if sec_counter >= 5:
                #                         lib_keyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)

                #                     # code by ravi

                #                     if sec_counter > 60:
                #                         break
                #     except KeyboardInterrupt:
                #         print("Keyboard Interrupt!")
                #         continue

                
                # key = lib_keypad.keypadHandler(FD_KEYPAD)
                # key_str = str(KEY_DICT[str(key)])
                # # if key_str == "1":
                # keys_taken = session.query(AMS_Keys).filter(AMS_Keys.keyStatus == 0).all()
                # if keys_taken != []:
                #     get_emergenecy_door_status(lib_display, FD_KEYPAD, ams_can, session, lib_KeyboxLock, cabinet, lib_Buzzer)


                # ############### code by ravi ###########################

                for keylistid in ams_can.key_lists:
                    ams_can.unlock_all_positions(keylistid)
                    ams_can.set_all_LED_OFF(keylistid)

                is_activity.is_active = 0
                session.commit()   
                ##########################################################

                key_str = ''
                key = lib_keypad.keypadHandler(FD_KEYPAD)
                key_str = str(KEY_DICT[str(key)])

                user_auth = None
                if key_str == "ENTER":

                    is_activity.is_active = 1
                    session.commit()

                    print("############   Step 2  ###########")
                    try:
                        # lib_display.displayString("                ".encode('utf-8'), 2)
                        # lib_display.displayString("Enter PIN: ".encode('utf-8'), 2)
                        global auth_mode
                        auth_mode, pin_entered, card_swiped = login_using_PIN_Card_Bio(lib_display, lib_keypad, FD_KEYPAD, session)
                        # Handle Home (UP) button: if user pressed Home, go back to main loop
                        if auth_mode is None:
                            continue
                        print("Auto mode :" + str(auth_mode) + " pin_entered = " + str(pin_entered) + " card no : " + str(card_swiped))
                        # lib_display.displayString("Validating PIN..".encode('utf-8'), 2)
                        if auth_mode > 0:
                            user_auth = ams_user.get_user_id(session, auth_mode, pin_no=pin_entered, card_no=card_swiped)
                        else:
                            continue
                        if user_auth["ResultCode"] == AUTH_RESULT_SUCCESS:
                            print("############   Step 3  ###########")
                            #print("User validated successfully - User Id: " + str(user_auth["id"]) + " Name "
                            #      + user_auth["name"])

                            user = session.query(AMS_Users).filter(and_(AMS_Users.pinCode == pin_entered, AMS_Users.cardNo == str(card_swiped))).one_or_none()
                            print(f"Details Entered: {pin_entered}, {str(card_swiped)}")
                            # print({c.name: getattr(user, c.name) for c in user.__table__.columns})
                            user.lastLoginDate = datetime.now(tz_IN)
                            session.commit()

                            user_str = ("Hi " + (user_auth["name"])[0:12]).ljust(15, ' ').encode('utf-8')

                            # Display Username for confirmation
                            lib_display.displayStringWithPosition(user_str, 2, 0)
                            sleep(2)

                            ams_access_log = AMS_Access_Log(signInTime=datetime.now(tz_IN), signInMode=get_auth_mode(),
                                                            signInFailed=0,signInSucceed=1, signInUserId=user_auth["id"],
                                                            activityCodeEntryTime=None, activityCode=None,
                                                            doorOpenTime=None, keysAllowed=None, keysTaken=None,
                                                            keysReturned=None, doorCloseTime=None,
                                                            event_type_id=EVENT_LOGIN_SUCCEES, is_posted=0)
                            session.add(ams_access_log)
                            session.commit()
                            # last_act_id = session.query(AMS_Access_Log).order_by(AMS_Access_Log.id.desc()).limit(1).one_or_none().id

                            login_type = ("PIN" if auth_mode == AUTH_MODE_PIN else "CARD+PIN" if auth_mode == AUTH_MODE_CARD_PIN else "BIO")

                            ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=None, activityId=None,
                                                          eventId=EVENT_LOGIN_SUCCEES, loginType=get_login_type(),
                                                          access_log_id=ams_access_log.id,
                                                          timeStamp=datetime.now(tz_IN), event_type=EVENT_TYPE_EVENT, is_posted=0)
                            session.add(ams_event_log)
                            session.commit()
                        else:
                            # print("Auto mode :" + str(auth_mode) + " pin_entered = " + str(
                            #     pin_entered) + " card no : " + str(card_swiped))
                            # return
                            #print("User validation failed - Message: " + user_auth["Message"])
                            user_str = str(user_auth["Message"]).ljust(16, ' ').encode('utf-8')
                            lib_display.displayStringWithPosition(user_str, 2, 0)
                            sleep(3)

                            # is_posted added by ravi
                            ams_access_log = AMS_Access_Log(signInTime=datetime.now(tz_IN), signInMode=get_auth_mode(), signInFailed=1,
                                                            signInSucceed=0, \
                                                            signInUserId=None, activityCodeEntryTime=None, activityCode=None,
                                                            doorOpenTime=None, \
                                                            keysAllowed=None, keysTaken=None, keysReturned=None,
                                                            doorCloseTime=None, event_type_id=EVENT_LOGIN_FAILED, is_posted=0)
                            session.add(ams_access_log)
                            session.commit()

                            # is_posted added by ravi
                            ams_event_log = AMS_Event_Log(userId=None, keyId=None, activityId=None,
                                                          eventId=EVENT_LOGIN_FAILED, loginType=get_login_type(),
                                                          access_log_id=ams_access_log.id,
                                                          timeStamp=datetime.now(tz_IN), event_type=EVENT_TYPE_EVENT, is_posted=0)
                            session.add(ams_event_log)
                            session.commit()
                            continue
                        if user_auth["ResultCode"] == AUTH_RESULT_SUCCESS:
                            print("############   Step 4  ###########")
                            try:
                                print("############   Step 5  ###########")
                                lib_display.displayString("                ".encode('utf-8'), 2)
                                lib_display.displayString("Activity Code:".encode('utf-8'), 2)
                                act_code_entered = get_activity_code(lib_display, lib_keypad, FD_KEYPAD)
                                # Handle Home (UP) button: if user pressed Home, go back to main loop
                                if act_code_entered is None:
                                    continue
                                ams_activities = AMS_Activities()
                                dic_result = ams_activities.get_keys_allowed(session, user_auth["id"],
                                                                             act_code_entered, datetime.now(tz_IN))

                                if dic_result["ResultCode"] == ACTIVITY_ALLOWED:
                                    print("############   Step 6  ###########")
                                    allowed_keys_list = None
                                    allowed_keys_list = dic_result["Message"].strip('][').split(',')
                                    print("\nAllowed Keys are : " + str(allowed_keys_list))

                                    # Save to DB
                                    ams_access_log.activityCodeEntryTime = datetime.now(tz_IN)
                                    ams_access_log.activityCode = act_code_entered
                                    ams_access_log.event_type_id = EVENT_TYPE_EVENT
                                    session.commit()

                                    # is_posted added by ravi
                                    ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=None,
                                                                  activityId=act_code_entered,
                                                                  eventId=EVENT_ACTIVITY_CODE_CORRECT,
                                                                  loginType=get_login_type(),
                                                                  access_log_id=ams_access_log.id,
                                                                  timeStamp=datetime.now(tz_IN),
                                                                  event_type=EVENT_TYPE_EVENT, is_posted=0)
                                    session.add(ams_event_log)
                                    session.commit()
                                    #Prepare key-strips = lock all except those which are allowed
                                    #print("\nAllowed key list : " + str(allowed_keys_list) + "\n")
                                    keys_OUT_STATUS_list = []
                                    keys_IN_STATUS_List = []
                                    keys_msg_In = '[IN :'
                                    keys_msg_Out = '[OUT:'
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
                                                    if key_record.keyStatus == SLOT_STATUS_KEY_NOT_PRESENT:
                                                        key_slot_no = key_record.keyPosition + (
                                                                    (key_record.keyStrip - 1) * 14)
                                                        keys_OUT_STATUS_list.append(key_record.id)
                                                        keys_msg_Out = keys_msg_Out + " K" + str(key_slot_no)

                                                        if not ams_can.get_key_id(key_record.keyStrip, key_record.keyPosition):
                                                            ams_can.set_single_key_lock_state(key_record.keyStrip,
                                                                                              key_record.keyPosition,
                                                                                              CAN_KEY_UNLOCKED)
                                                            ams_can.set_single_LED_state(key_record.keyStrip,
                                                                                         key_record.keyPosition,
                                                                                         CAN_LED_STATE_ON)
                                                        else:
                                                            print("\nAnother Key already present in the slot!!!! ")
 
                                                        # lib_display.displayStringWithPosition(" Return the key ".encode('utf-8'), 1, 0)
                                                        # lib_display.displayStringWithPosition(keys_msg_Out.encode('utf-8'), 2, 0)

                                                    elif key_record.keyStatus == SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT:
                                                        if key_record.keyName in load_prompted_keys():
                                                            remove_prompted_key(key_record.keyName)
                                                            # PROMPTED_KEYS.remove(key_record.keyName)

                                                        key_slot_no = key_record.keyPosition + (
                                                                (key_record.keyStrip - 1) * 14)
                                                        keys_IN_STATUS_List.append(key_record.id)
                                                        keys_msg_In = keys_msg_In + " K" + str(key_slot_no)

                                                        ams_can.set_single_key_lock_state(key_record.current_pos_strip_id,
                                                                                          key_record.current_pos_slot_no,
                                                                                          CAN_KEY_UNLOCKED)
                                                        ams_can.set_single_LED_state(key_record.current_pos_strip_id,
                                                                                     key_record.current_pos_slot_no,
                                                                                     CAN_LED_STATE_ON)

                                                        # lib_display.displayStringWithPosition("  Take the key ".encode('utf-8'), 1, 0)
                                                        # lib_display.displayStringWithPosition(keys_msg_In.encode('utf-8'), 2, 0)

                                                    elif key_record.keyStatus == SLOT_STATUS_KEY_PRESENT_WRONG_SLOT:
                                                        if key_record.keyName in load_prompted_keys():
                                                            remove_prompted_key(key_record.keyName)
                                                        key_slot_no = key_record.keyPosition + (
                                                                (key_record.keyStrip - 1) * 14)
                                                        keys_IN_STATUS_List.append(key_record.id)
                                                        keys_msg_In = keys_msg_In + " K" + str(key_slot_no)

                                                        ams_can.set_single_key_lock_state(key_record.current_pos_strip_id,
                                                                                          key_record.current_pos_slot_no,
                                                                                          CAN_KEY_UNLOCKED)
                                                        ams_can.set_single_LED_state(key_record.current_pos_strip_id,
                                                                                     key_record.current_pos_slot_no,
                                                                                     CAN_LED_STATE_BLINK)

                                                        # lib_display.displayStringWithPosition("Take Key:Wrong-P".encode('utf-8'), 1, 0)
                                                        # lib_display.displayStringWithPosition(keys_msg_In.encode('utf-8'), 2, 0)
                                                    break
                                    print("############   Step 8  ###########")
                                    keys_msg_In = keys_msg_In + "]"
                                    keys_msg_Out = keys_msg_Out + "]"
                                    msg_line_1 = ((keys_msg_In + keys_msg_Out)[:16]).encode('utf-8')
                                    msg_line_2 = ((keys_msg_In + keys_msg_Out)[16:]).encode('utf-8')
                                    lib_display.displayClear()
                                    lib_display.displayString(msg_line_1, 1)
                                    lib_display.displayString(msg_line_2, 2)

                                    lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_UN_LOCK)
                                    # ams_can.lib_door_lock.setKeyBoxLock(ams_can.Lock_FD, 1, 1, 1)
                                    # ams_can.door_closed_status = False
                                    # Save to DB
                                    ams_access_log.doorOpenTime = datetime.now(tz_IN)
                                    ams_access_log.event_type_id = EVENT_TYPE_EVENT
                                    session.commit()

                                    # is_posted added by ravi
                                    ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=None,
                                                                  activityId=act_code_entered,
                                                                  eventId=EVENT_DOOR_OPEN,
                                                                  loginType=get_login_type(),
                                                                  access_log_id=ams_access_log.id,
                                                                  timeStamp=datetime.now(tz_IN),
                                                                  event_type=EVENT_TYPE_EVENT, is_posted=0)
                                    session.add(ams_event_log)
                                    session.commit()
                                    # Wait till user takes/returns keys and closes the door
                                    # Make list of keys taken or keys returned
                                    sec_counter = 0
                                    door_is_open = False
                                    while True:
                                        print("############   Step 9  ###########")
                                        door_status = lib_KeyboxLock.getDoorSensorStatus1()
                                        sleep(1)
                                        sec_counter += 1
                                        if door_status == 0:
                                            door_is_open = True
                                            break
                                        elif door_status == 1 and sec_counter >= 5:
                                            door_is_open = False
                                        # following condition seems to be un-necessary
                                        if sec_counter > 10:
                                            door_is_open = True
                                            break

                                    sec_counter = 0
                                    keys_taken_list = []
                                    keys_returned_list = []
                                    door_opened_too_long_status = False
                                    while door_is_open:
                                    # while sec_counter < 30:

                                        print("############   Step 10  ###########")

                                        sec_counter += 1
                                        key_record = None

                                        if sec_counter == 3:
                                            lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                                            # ams_can.lib_door_lock.setKeyBoxLock(ams_can.Lock_FD, 1, 1, 0)
                                            # ams_can.door_closed_status = True
                                        elif sec_counter >= 60:
                                            door_opened_too_long_status = True
                                            lib_display.displayClear()
                                            lib_display.displayString("Door opened too ".encode('utf-8'), 1)
                                            lib_display.displayString("long, close door".encode('utf-8'), 2)
                                            
                                            lib_Buzzer.setBuzzerOn()

                                        if ams_can.key_taken_event:
                                            print("############   Step 11  ###########")
                                            print("\n\nKEY Taken\n\n")
                                            for key in cabinet.keys:
                                                if key.peg_id == ams_can.key_taken_id:
                                                    key_record = key
                                            if key_record:
                                                keys_msg_print = ("Key taken: " + (key_record.keyName.ljust(4, ' '))).encode('utf-8')
                                                print(keys_msg_print)
                                                ams_access_log.keysTaken = str(key_record.id)
                                                session.commit()
                                                session.query(AMS_Keys).filter(
                                                    AMS_Keys.peg_id == ams_can.key_taken_id).update(
                                                    {'keyTakenBy': user_auth["id"],
                                                     'keyTakenByUser': user_auth["name"],
                                                     'current_pos_strip_id': ams_can.key_taken_position_list,
                                                     'current_pos_slot_no': ams_can.key_taken_position_slot,
                                                     'keyTakenAtTime': datetime.now(tz_IN),
                                                     'keyStatus': SLOT_STATUS_KEY_NOT_PRESENT})
                                                session.commit()

                                                # is_posted added by ravi
                                                ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=key_record.id,
                                                                              activityId=act_code_entered,
                                                                              eventId=EVENT_KEY_TAKEN_CORRECT,
                                                                              loginType=get_login_type(),
                                                                              access_log_id=ams_access_log.id,
                                                                              timeStamp=datetime.now(tz_IN),
                                                                              event_type=EVENT_TYPE_EVENT, is_posted=0)
                                                session.add(ams_event_log)
                                                session.commit()

                                                if key_record.keyName not in keys_taken_list:
                                                    keys_taken_list.append(key_record.keyName)
                                                    # add_prompted_key(key_record.keyName)
                                                # if key_record.keyName in keys_returned_list:
                                                #     keys_returned_list.remove(key_record.keyName)
                                            else:
                                                print("Key taken but key record not found for updating taken event")
                                                keys_msg_print = ("Key not reg.    ".encode('utf-8'))

                                            lib_display.displayClear()
                                            lib_display.displayString(keys_msg_print, 2)
                                            sleep(2)
                                            ams_can.key_taken_event = False

                                        if ams_can.key_inserted_event:
                                            print("############   Step 12  ###########")
                                            print("\n\nKEY INSERTED\n\n")
                                            for key in cabinet.keys:
                                                #print("\nkey.peg_id = " + str(key.peg_id))
                                                #print("\nams_can.key_inserted_id = " + str(ams_can.key_inserted_id))
                                                if key.peg_id == ams_can.key_inserted_id:
                                                    key_record = key
                                                    #print("\nKey return records : " + str(key) + "\n")

                                            if key_record:
                                                if key_record.keyStrip == ams_can.key_inserted_position_list and \
                                                        key_record.keyPosition == ams_can.key_inserted_position_slot:
                                                    ams_can.set_single_LED_state(ams_can.key_inserted_position_list,
                                                                                 ams_can.key_inserted_position_slot,
                                                                                 CAN_LED_STATE_OFF)
                                                    keys_msg_print = ("Key return:" + (
                                                        key_record.keyName.ljust(4, ' '))).encode('utf-8')
                                                    ams_access_log.keysReturned = str(key_record.id)
                                                    session.commit()

                                                    session.query(AMS_Keys).filter(
                                                        AMS_Keys.peg_id == ams_can.key_inserted_id).update(
                                                        {'current_pos_door_id': 1,
                                                         'keyTakenBy': None,
                                                         'keyTakenAtTime': None,
                                                         'current_pos_strip_id': ams_can.key_inserted_position_list,
                                                         'current_pos_slot_no': ams_can.key_inserted_position_slot,
                                                         'keyStatus': SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT})
                                                    session.commit()

                                                    overdue_logged = session.query(AMS_Event_Log).filter_by(
                                                        keyId=key_record.id,
                                                        # eventId=19  # EVENT_KEY_OVERDUE
                                                    ).order_by(AMS_Event_Log.id.desc()).first()
                                                    
                                                    event_id_to_log = EVENT_KEY_RETURNED_RIGHT_SLOT
                                                    event_Type = EVENT_TYPE_EVENT

                                                    print("DEBUG overdue_logged:", {c.name: getattr(overdue_logged, c.name) for c in overdue_logged.__table__.columns})

                                                    if overdue_logged and overdue_logged.eventId == 19:  # EVENT_KEY_OVERDUE

                                                        event_id_to_log = 31
                                                        event_Type = EVENT_TYPE_EXCEPTION
                                                    
                                                    print(f"Overdue event is being triggered overdue_logged event_id_to_log: {event_id_to_log}")

                                                    ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=key_record.id,
                                                                                  activityId=act_code_entered,
                                                                                  eventId=event_id_to_log,
                                                                                  loginType=get_login_type(),
                                                                                  access_log_id=ams_access_log.id,
                                                                                  timeStamp=datetime.now(tz_IN),
                                                                                  event_type=event_Type, is_posted=0)
                                                    session.add(ams_event_log)
                                                    session.commit()

                                                    # Log overdue key returned if applicable
                                                    overdue_logged = session.query(AMS_Event_Log).filter_by(
                                                        keyId=key_record.id,
                                                        eventId=19  # EVENT_KEY_OVERDUE
                                                    ).order_by(AMS_Event_Log.id.desc()).first()
                                                    overdue_return_logged = session.query(AMS_Event_Log).filter_by(
                                                        keyId=key_record.id,
                                                        eventId=EVENT_KEY_OVERDUE_RETURNED  # EVENT_KEY_OVERDUE_RETURNED
                                                    ).order_by(AMS_Event_Log.id.desc()).first()
                                                    
                                                    print(f"Overdue event is being triggered overdue_return_logged:  {overdue_return_logged}, overdue_logged: {overdue_logged}")
                                                    if overdue_logged and not overdue_return_logged:
                                                        try:
                                                            ams_event_log = AMS_Event_Log(
                                                                userId=user_auth["id"],
                                                                keyId=key_record.id,
                                                                activityId=None,
                                                                eventId=EVENT_KEY_OVERDUE_RETURNED,  # EVENT_KEY_OVERDUE_RETURNED
                                                                loginType=get_login_type(),
                                                                access_log_id=ams_access_log.id,
                                                                timeStamp=datetime.now(tz_IN),
                                                                event_type=EVENT_TYPE_EXCEPTION,
                                                                is_posted=0,
                                                            )
                                                            session.add(ams_event_log)
                                                            session.commit()
                                                            print("Evnet Overdue Logged!!!!!!!!!!!!!!!!!!!!")
                                                        except Exception as e:
                                                            print(f"Exception while logging overdue key return: {e}")
                                                    lib_display.displayClear()
                                                    lib_display.displayString(keys_msg_print, 2)
                                                    ams_can.key_inserted_event = False
                                                    if key_record.keyName not in keys_returned_list:
                                                        keys_returned_list.append(key_record.keyName)
                                                        if key_record.keyName in load_prompted_keys(): 
                                                            remove_prompted_key(key_record.keyName)
                                                    # if key_record.keyName in keys_taken_list:
                                                    #     keys_taken_list.remove(key_record.keyName)

                                                elif key_record.keyStrip != ams_can.key_inserted_position_list or \
                                                        key_record.keyPosition != ams_can.key_inserted_position_slot:
                                                    ams_can.set_single_LED_state(ams_can.key_inserted_position_list,
                                                                                 ams_can.key_inserted_position_slot,
                                                                                 CAN_LED_STATE_BLINK)
                                                    keys_msg_print = ("Key return:" + (
                                                        key_record.keyName.ljust(4, ' '))).encode('utf-8')

                                                    ams_access_log.keysReturned = str(key_record.id)
                                                    session.commit()

                                                    session.query(AMS_Keys).filter(
                                                        AMS_Keys.peg_id == ams_can.key_inserted_id).update(
                                                        {'current_pos_door_id': 1,
                                                         'current_pos_strip_id': ams_can.key_inserted_position_list,
                                                         'current_pos_slot_no': ams_can.key_inserted_position_slot,
                                                         'keyStatus': SLOT_STATUS_KEY_PRESENT_WRONG_SLOT})
                                                    session.commit()

                                                    ams_event_log = AMS_Event_Log(userId=user_auth["id"],
                                                                                  keyId=key_record.id,
                                                                                  activityId=act_code_entered,
                                                                                  eventId=EVENT_KEY_RETURNED_WRONG_SLOT,
                                                                                  loginType=get_login_type(),
                                                                                  access_log_id=ams_access_log.id,
                                                                                  timeStamp=datetime.now(tz_IN),
                                                                                  event_type=EVENT_TYPE_ALARM, is_posted=0)
                                                    session.add(ams_event_log)
                                                    session.commit()
                                                    lib_display.displayClear()
                                                    lib_display.displayString(keys_msg_print, 2)
                                                    
                                                    ams_can.key_inserted_event = False
                                                    IS_KEY_IN_WRONG_SLOT = True

                                                    if not ams_can.get_key_id(key_record.keyStrip,
                                                                              key_record.keyPosition):
                                                        ams_can.set_single_key_lock_state(ams_can.key_inserted_position_list,
                                                                                          ams_can.key_inserted_position_slot,
                                                                                          CAN_KEY_UNLOCKED)
                                                        ams_can.set_single_LED_state(ams_can.key_inserted_position_list,
                                                                                     ams_can.key_inserted_position_slot,
                                                                                     CAN_LED_STATE_BLINK)
                                                        ams_can.set_single_key_lock_state(key_record.keyStrip,
                                                                                          key_record.keyPosition,
                                                                                          CAN_KEY_UNLOCKED)
                                                        ams_can.set_single_LED_state(key_record.keyStrip,
                                                                                     key_record.keyPosition,
                                                                                     CAN_LED_STATE_ON)

                                                        correct_key_POS = (key_record.keyPosition + ((key_record.keyStrip-1)*14))
                                                        current_key_POS = (ams_can.key_inserted_position_slot + (
                                                                    (ams_can.key_inserted_position_list - 1) * 14))
                                                        msg_line1 = ("Wrong slot  " + str(current_key_POS) + "  ").encode('utf-8')
                                                        msg_line2 = ("Put in slot " + str(correct_key_POS) + "  ").encode('utf-8')
                                                        lib_display.displayString(msg_line1, 1)
                                                        lib_display.displayString(msg_line2, 2)
                                                        sleep(3)
                                                        if key_record.id not in keys_returned_list:
                                                            keys_returned_list.append(key_record.id)
                                                        if key_record.id in keys_taken_list:
                                                            keys_taken_list.remove(key_record.id)
                                                    else:
                                                        msg_line1 = "Key in wrong pos".encode('utf-8')
                                                        msg_line2 = "Correct pos n/a ".encode('utf-8')
                                                        lib_display.displayClear()
                                                        lib_display.displayString(msg_line1, 1)
                                                        lib_display.displayString(msg_line2, 2)
                                                        sleep(3)
                                                    IS_KEY_IN_WRONG_SLOT_Correct_Strip = key_record.keyStrip
                                                    IS_KEY_IN_WRONG_SLOT_Correct_Pos = key_record.keyPosition
                                                    IS_KEY_IN_WRONG_SLOT_Wrong_Strip = ams_can.key_inserted_position_list
                                                    IS_KEY_IN_WRONG_SLOT_Wrong_Pos = ams_can.key_inserted_position_slot
                                                    IS_KEY_IN_WRONG_SLOT_User_PIN = pin_entered
                                                    lib_Buzzer.setBuzzerOn()
                                                    sleep(5)
                                                    lib_Buzzer.setBuzzerOff()
                                                    if key_record.keyName not in keys_returned_list:
                                                        keys_returned_list.append(key_record.keyName)
                                                    # if key_record.keyName in keys_taken_list:
                                                    #     keys_taken_list.remove(key_record.keyName)

                                            

                                            else:
                                                print("Key inserted but key record not found for updating inserted event")
                                                msg_line1 = "Key record n/a  ".encode('utf-8')
                                                msg_line2 = "Register the key".encode('utf-8')
                                                lib_display.displayClear()
                                                lib_display.displayString(msg_line1, 1)
                                                lib_display.displayString(msg_line2, 2)
                                                sleep(1)

                                        door_status = lib_KeyboxLock.getDoorSensorStatus1()
                                        sleep(1)
                                        if door_status == 0:
                                            door_is_open = True
                                        elif door_status == 1:
                                            door_is_open = False
                                    print(f"door_opened_too_long_status: {door_opened_too_long_status}")
                                    if door_opened_too_long_status:
                                        print("DEBUG userId:", user_auth["id"])
                                        print("DEBUG keyId:", None)
                                        print("DEBUG activityId:", act_code_entered)
                                        print("DEBUG eventId:", EVENT_DOOR_OPENED_TOO_LONG)
                                        print("DEBUG loginType:", get_login_type())
                                        print("DEBUG access_log_id:", ams_access_log.id if ams_access_log else None)
                                        print("DEBUG timeStamp:", datetime.now(tz_IN))
                                        print("DEBUG event_type:", EVENT_TYPE_ALARM)
                                        print("DEBUG is_posted:", 0)
                                        ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=None,
                                                                              activityId=act_code_entered,
                                                                              eventId=EVENT_DOOR_OPENED_TOO_LONG,
                                                                              loginType=get_login_type(),
                                                                              access_log_id=ams_access_log.id,
                                                                              timeStamp=datetime.now(tz_IN),
                                                                              event_type=EVENT_TYPE_ALARM, is_posted=0)
                                        session.add(ams_event_log)
                                        session.commit()
                                        door_opened_too_long_status = False
                                    print("############   Step 13  ###########")
                                    lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                                    # ams_can.lib_door_lock.setKeyBoxLock(ams_can.Lock_FD, 1, 1, 0)
                                    # ams_can.door_closed_status = True
                                    lib_Buzzer.setBuzzerOff()
                                    ams_can.lock_all_positions(1)
                                    ams_can.set_all_LED_OFF(1)
                                    ams_can.lock_all_positions(2)
                                    ams_can.set_all_LED_OFF(2)
                                    # print("\nNo of keylists after activity : " + str(len(ams_can.key_lists)))
                                    # for keylistid in ams_can.key_lists:
                                    #     ams_can.lock_all_positions(keylistid)
                                    #     ams_can.set_all_LED_OFF(keylistid)
                                    #     sleep(0.5)
                                    lib_display.displayString("  Door Closed  ".encode('utf-8'), 2)
                                    sleep(1)
                                    ams_access_log.doorCloseTime = datetime.now(tz_IN)
                                    ams_access_log.keysAllowed = str(allowed_keys_list)
                                    ams_access_log.keysTaken = str(keys_taken_list)
                                    ams_access_log.keysReturned = str(keys_returned_list)
                                    ams_access_log.event_type_id = EVENT_TYPE_EVENT
                                    session.commit()


                                    # code by ravi 
                                    # if not act_code_entered in pending_acts.keys():
                                    #     pending_acts[act_code_entered] = {last_act_id : keys_taken_list}
                                    # else:
                                    #     for act_id, keys_taken in pending_acts[act_code_entered].items():
                                    #         access_log = session.query(AMS_Access_Log).filter(AMS_Access_Log.id == act_id).one_or_none()
                                    #         if sorted(keys_returned_list) == sorted(keys_taken):
                                    #             print("all keys returned")
                                    #             access_log.doorCloseTime = datetime.now(tz_IN)
                                    #             access_log.keysReturned = str(keys_returned_list)
                                    #             session.commit()
                                    #             del pending_acts[act_code_entered]
                                    #         else:
                                    #             print("some keys are returned")
                                    #             temp = []
                                    #             for key_ret in keys_returned_list:
                                    #                 if key_ret in keys_taken:
                                    #                     keys_taken.remove(key_ret)
                                    #                     temp.append(key_ret)
                                    #             if len(keys_taken) == 0:
                                    #                 access_log.doorCloseTime = datetime.now(tz_IN)
                                    #                 access_log.keysReturned = str(json.loads(access_log.keysReturned).extend(temp))
                                    #                 session.commit()
                                    #                 del pending_acts[act_code_entered]
                                    #             else:
                                    #                 access_log.keysReturned = str(json.loads(access_log.keysReturned).extend(temp))
                                    #                 session.commit()
                                    #                 pending_acts[act_code_entered][act_id] = keys_taken
                                    
                                    # print(f'*************\n{pending_acts}\n****************')
                                    # code by ravi
                                    

                                    # is_posted added by ravi
                                    ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=None,
                                                                  activityId=act_code_entered,
                                                                  eventId=EVENT_DOOR_CLOSED,
                                                                  loginType=get_login_type(),
                                                                  access_log_id=ams_access_log.id,
                                                                  timeStamp=datetime.now(tz_IN),
                                                                  event_type=EVENT_TYPE_EVENT, is_posted=0)
                                    session.add(ams_event_log)
                                    session.commit()

                                    print("\n\nKeys taken: " + str(keys_taken_list) + "\nKeys returned: " + str(keys_returned_list) + "\n\n")
                                    alarm_for_previous_keys(session, lib_display, lib_Buzzer)

                                    with open('ack.cnt', 'w') as fAck:
                                        fAck.write(str(0))
                                        fAck.close()
                                    print("############   Step 14  ###########")
                                    if IS_KEY_IN_WRONG_SLOT:
                                        sleep(1)
                                        lib_display.displayString("Key in Wrong Pos".encode('utf-8'), 1)

                                        keys_msg = "[S" + str(IS_KEY_IN_WRONG_SLOT_Wrong_Strip) + "P" + str(
                                            IS_KEY_IN_WRONG_SLOT_Wrong_Pos) + "]->[S" + str(
                                            IS_KEY_IN_WRONG_SLOT_Correct_Strip) + "P" + str(
                                            IS_KEY_IN_WRONG_SLOT_Correct_Pos) + "]"
                                        IS_KEY_IN_WRONG_SLOT_Message = keys_msg
                                        lib_display.displayString(keys_msg.encode('utf-8'), 2)
                                        lib_keypad.keypadHandler(FD_KEYPAD)
                                        IS_KEY_IN_WRONG_SLOT = False
                                    continue
                                else:
                                    # is_posted added by ravi
                                    ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=None, activityId=act_code_entered,
                                                                  eventId=EVENT_ACTIVITY_CODE_NOT_ALLOWED, loginType=get_login_type(),
                                                                  access_log_id=ams_access_log.id,
                                                                  timeStamp=datetime.now(tz_IN), event_type=EVENT_TYPE_EVENT, is_posted=0)
                                    session.add(ams_event_log)
                                    session.commit()
                                    print("Activity Code not accepted: Reason - " + dic_result["Message"])
                                    lib_display.displayString((dic_result["Message"]).ljust(16, ' ').encode('utf-8'), 2)
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
                elif key_str == 'F1':

                    # ############### code by ravi ###########################
                    is_activity.is_active = 1
                    session.commit()
                    ##########################################################

                    # admin panel for keypress F1
                    print("############   Step 18  ###########")
                    lib_display.displayString("                ".encode('utf-8'), 2)
                    lib_display.displayString("Admin PIN: ".encode('utf-8'), 2)
                    pin_entered = login_using_PIN(lib_display, lib_keypad, FD_KEYPAD)
                    print("pin Entered: "+str(pin_entered))
                    lib_display.displayString("Validating PIN..".encode('utf-8'), 2)
                    if not (pin_entered == ''):
                        print("############   Step 19  ###########")
                        user_auth = ams_user.get_user_id(session, AUTH_MODE_PIN, pin_no=pin_entered)
                        if user_auth["ResultCode"] == AUTH_RESULT_SUCCESS:
                            print("############   Step 20  ###########")
                            # Below query not working --
                            # roleName = session.query(ams_cabinet.roles.roleName).filter(ams_cabinet.roles.id
                            #                                                            == user_auth["roleId"]).first()

                            roleId = user_auth["roleId"]
                            if roleId == 1:
                                print("############   Step 21  ###########")
                                key_str = None
                                while True:
                                    # Show first 3 options for 3 seconds
                                    lib_display.displayClear()
                                    lib_display.displayString("1.Reg.Card 2.Bio".encode('utf-8'), 1)
                                    lib_display.displayString("3.Peg Reg.".encode('utf-8'), 2)
                                    start_time = time.time()
                                    while time.time() - start_time < 3:
                                        key = lib_keypad.keypadHandler(FD_KEYPAD)
                                        key_str = str(KEY_DICT[str(key)])
                                        if key_str in ["1", "2", "3", "4", "5", "F1"]:
                                            break
                                        time.sleep(0.1)
                                    else:
                                        # No key pressed, show next options
                                        lib_display.displayClear()
                                        lib_display.displayString("4.D/T Set".encode('utf-8'), 1)
                                        lib_display.displayString("5.NetConf".encode('utf-8'), 2)
                                        start_time = time.time()
                                        while time.time() - start_time < 3:
                                            key = lib_keypad.keypadHandler(FD_KEYPAD)
                                            key_str = str(KEY_DICT[str(key)])
                                            if key_str in ["1", "2", "3", "4", "5", "F1"]:
                                                break
                                            time.sleep(0.1)
                                        else:
                                            continue  # No key pressed, repeat cycle
                                        break  # Key pressed, break out of loop
                                    break  # Key pressed, break out of loop

                                # Now handle the key_str as before
                                if key_str == "1":
                                    print("############   Step 22  ###########")
                                    lib_display.displayClear()
                                    lib_display.displayString("Enter User PIN".encode('utf-8'), 1)
                                    pin_entered = login_using_PIN(lib_display, lib_keypad, FD_KEYPAD)
                                    lib_display.displayString("Validating PIN..".encode('utf-8'), 2)
                                    print(f'entered pin is: {pin_entered}')
                                    if not (pin_entered == ''):
                                        user_auth = ams_user.get_user_id(session, AUTH_MODE_PIN, pin_no=pin_entered)
                                        # print("user Auth : " + str(user_auth))
                                        if user_auth["ResultCode"] == AUTH_RESULT_SUCCESS:
                                            lib_display.displayClear()
                                            lib_display.displayString("Swipe User Card ".encode('utf-8'), 1)
                                            timer_sec = 0
                                            card_no = None
                                            card_no_updated = False
                                            while timer_sec < 80:
                                                timer_sec += 1
                                                card_no = amsbms.cardNo
                                                sleep(0.25)
                                                print(f'card number is: {card_no}')
                                                if str(card_no) != "0":
                                                    print("\nInside test for Card Exists!")

                                                    try:
                                                        is_already_assigned = session.query(AMS_Users).filter(
                                                            AMS_Users.cardNo == str(card_no)).one_or_none()
                                                    except Exception as e:
                                                        print(e)
                                                    print("IS is_assigned object NONE?? " + str(
                                                        (is_already_assigned is None)))
                                                    if (is_already_assigned is not None):
                                                        print("Username with same card is: found")

                                                        # eventDesc = get_event_description(
                                                        #     session,
                                                        #     EVENT_CARD_ASSIGNMENT_FAILURE,
                                                        # )
                                                        # print("Username with same card is: found")
                                                        # ams_event_log = AMS_Event_Log(
                                                        #     userId=user_auth["id"],
                                                        #     keyId=None,
                                                        #     activityId=1,
                                                        #     eventId=EVENT_CARD_ASSIGNMENT_FAILURE,
                                                        #     loginType="PIN+Card",
                                                        #     access_log_id=ams_access_log.id,
                                                        #     timeStamp=datetime.now(
                                                        #         TZ_INDIA
                                                        #     ),
                                                        #     event_type=EVENT_TYPE_ALARM,
                                                        #     eventDesc=eventDesc,
                                                        #     is_posted=0,
                                                        # )
                                                        # print("Username with same card is: found")
                                                        # session.add(ams_event_log)
                                                        # session.commit()
                                                        # print("Username with same card is: found")
                                                        lib_display.displayClear()
                                                        lib_display.displayString("Card Already".encode('utf-8'), 1)
                                                        lib_display.displayString("Assigned".encode('utf-8'), 2)
                                                        sleep(2)
                                                        print("Username with same card is: found 5")
                                                        card_no_updated = False

                                                        break
                                                    else:
                                                        session.query(AMS_Users).filter(
                                                            AMS_Users.id == user_auth["id"]
                                                        ).update({"cardNo": str(card_no)})
                                                        card_no_updated = True
                                                        break

                                            if card_no_updated:
                                                lib_display.displayClear()
                                                lib_display.displayString("Card Registered".encode('utf-8'), 1)
                                                msg = "for " + user_auth["name"]
                                                lib_display.displayString(msg.encode('utf-8'), 2)
                                                ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=None,
                                                                              activityId=None,
                                                                              eventId=EVENT_CARD_REG_DONE,
                                                                              loginType=get_login_type(),
                                                                              access_log_id=None,
                                                                              timeStamp=datetime.now(tz_IN),
                                                                              event_type=EVENT_TYPE_EVENT, is_posted=0)
                                                session.add(ams_event_log)
                                                session.commit()
                                                sleep(5)
                                            else:
                                                lib_display.displayClear()
                                                lib_display.displayString("Card not reg.".encode('utf-8'), 1)
                                                lib_display.displayString("Try again later.".encode('utf-8'), 2)
                                                ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=None,
                                                                              activityId=None,
                                                                              eventId=EVENT_CARD_REG_FAILED,
                                                                              loginType=get_login_type(),
                                                                              access_log_id=None,
                                                                              timeStamp=datetime.now(tz_IN),
                                                                              event_type=EVENT_TYPE_EVENT, is_posted=0)
                                                session.add(ams_event_log)
                                                session.commit()
                                                sleep(5)
                                            continue
                                elif key_str == "2":
                                    lib_display.displayClear()
                                    lib_display.displayString("Enter User PIN".encode('utf-8'), 1)
                                    pin_entered = login_using_PIN(lib_display, lib_keypad, FD_KEYPAD)
                                    lib_display.displayString("Validating PIN..".encode('utf-8'), 2)
                                    if not (pin_entered == ''):
                                        user_auth = ams_user.get_user_id(session, AUTH_MODE_PIN, pin_no=pin_entered)
                                        # print("user Auth : " + str(user_auth))
                                        if user_auth["ResultCode"] == AUTH_RESULT_SUCCESS:
                                            lib_display.displayClear()
                                            lib_display.displayString("Scan finger now ".encode('utf-8'), 1)

                                            if os.path.exists("frame_Ex.bmp"):
                                                os.remove("frame_Ex.bmp")
                                                print("file removed")
                                            if os.path.exists("user_template"):
                                                os.remove("user_template")
                                                print("biometric file removed")

                                            print("PLease place finger on scanner...")

                                            return_val = subprocess.run("/home/ams-core/ftrScanAPI_Ex")

                                            print("Return value from ftrScanAPI. : " + str(return_val))

                                            lib_display.displayString("Scan complete...".encode('utf-8'), 1)
                                            lib_display.displayString("Validating, pls wait".encode('utf-8'), 2)
                                            
                                            enroll_data = subprocess.run(
                                                ["/home/ams-core/FCEnrollFingerFromImageCPP", "frame_Ex.bmp", "user_template"],
                                                capture_output=True,
                                                text=True
                                            )

                                            print("STDOUT:", enroll_data.stdout)
                                            print("STDERR:", enroll_data.stderr)
                                            print("Return code:", enroll_data.returncode)

                                            print("enroll finger data: " + str(enroll_data))

                                            with open('user_template', 'rb') as f:
                                                ablob = f.read()

                                            
                                            match = validate_fingerprint_user(session)
                                            if match:
                                                existing_user, score = match
                                                if existing_user.pinCode != pin_entered:
                                                    # Finger already registered to another user → block registration
                                                    lib_display.displayClear()
                                                    lib_display.displayString("FP already exists".encode('utf-8'), 1)
                                                    lib_display.displayString(f"User PIN: {existing_user.name}".encode('utf-8'), 2)
                                                    print(f"Error: Fingerprint already registered for user {existing_user.pinCode}")
                                                    sleep(3)
                                                    lib_display.displayString("Please try again".encode('utf-8'), 1)
                                                    lib_display.displayString(f"".encode('utf-8'), 2)
                                                    
                                                    ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=None,
                                                                              activityId=None,
                                                                              eventId=EVENT_BIO_REG_FAILED,
                                                                              loginType="BIO",
                                                                              access_log_id=None,
                                                                              timeStamp=datetime.now(tz_IN),
                                                                              event_type=EVENT_TYPE_EVENT, is_posted=0)
                                                    session.add(ams_event_log)
                                                    session.commit()
                                                    continue 

                                            session.query(AMS_Users).filter(AMS_Users.pinCode == pin_entered).update(
                                                {"fpTemplate": memoryview(ablob)})
                                            session.commit()
                                            lib_display.displayString("FP registration ".encode('utf-8'), 1)
                                            lib_display.displayString("done, pls wait  ".encode('utf-8'), 2)

                                            print("Fingerprint registered for user with PIN: " + str(pin_entered))
                                            ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=None,
                                                                              activityId=None,
                                                                              eventId=EVENT_BIO_REG_DONE,
                                                                              loginType="BIO",
                                                                              access_log_id=None,
                                                                              timeStamp=datetime.now(tz_IN),
                                                                              event_type=EVENT_TYPE_EVENT, is_posted=0)
                                            try:
                                                session.add(ams_event_log)
                                                session.commit()
                                                print("✅ AMS_Event_Log inserted successfully:")
                                                print(f"   ID: {ams_event_log.id}, UserID: {ams_event_log.userId}, Event: {ams_event_log.eventId}, LoginType: {ams_event_log.loginType}")

                                                
                                                url = "http://192.168.1.188:8000/eventLogController/list"  
                                                payload = {}   # no filters, get all
                                                headers = {"Content-Type": "application/json"}

                                                response = requests.post(url, json=payload, headers=headers)
                                                if response.status_code == 200:
                                                    data = response.json()
                                                    logs = data.get("data", [])[:5]  # take top 5
                                                    print("📜 Top 5 Recent Event Logs (from API):")
                                                    for log in logs:
                                                        print(f"   ID={log['id']} | Time={log['timeStamp']} | Event={log['Event']['eventName']} | User={log['User']['name']} | LoginType={log['loginType']}")
                                                else:
                                                    print("❌ API call failed:", response.status_code, response.text)
                                            except Exception as e:
                                                print("❌ Failed to Log AMS_Event_Log:", str(e))
                                            sleep(2)
                                            continue
                                elif key_str == "F1":
                                    continue
                                elif key_str == "3":
                                    # Un-lock Door and un-lock all locks
                                    #print("** No of keylist : " + str(len(ams_can.key_lists)))
                                    for keylistid in ams_can.key_lists:
                                        ams_can.unlock_all_positions(keylistid)
                                        ams_can.set_all_LED_ON(keylistid, False)

                                    lib_display.displayString("                ".encode('utf-8'), 1)
                                    lib_display.displayString("Open door...    ".encode('utf-8'), 2)
                                    lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_UN_LOCK)
                                    # ams_can.lib_door_lock.setKeyBoxLock(ams_can.Lock_FD, 1, 1, 1)
                                    # ams_can.door_closed_status = False
                                    sec_counter = 0
                                    while True:
                                        print("############   Waiting for Door to open  ###########")
                                        door_status = lib_KeyboxLock.getDoorSensorStatus1()
                                        sleep(1)
                                        sec_counter += 1
                                        if door_status == 0 and sec_counter >= 5:
                                            lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                                            break
                                        if sec_counter > 5:
                                            lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                                            break
                                    # If door is not opened, getting user back to main screen
                                    if door_status != MAIN_DOOR_LOCK:
                                        for keylistid in ams_can.key_lists:
                                            ams_can.lock_all_positions(keylistid)
                                            ams_can.set_all_LED_OFF(keylistid)
                                        lib_display.displayString("WELCOME AMS V1.1".encode('utf-8'), 1)
                                        continue

                                    lib_display.displayString("Insert all keys ".encode('utf-8'), 1)
                                    lib_display.displayString("and press ENTER ".encode('utf-8'), 2)
                                    key = lib_keypad.keypadHandler(FD_KEYPAD)
                                    key_str = str(KEY_DICT[str(key)])
                                    if key_str == "ENTER":
                                        # lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                                        # ams_can.lib_door_lock.setKeyBoxLock(ams_can.Lock_FD, 1, 1, 0)
                                        # ams_can.door_closed_status = True

                                        lib_display.displayString("Scan in progress".encode('utf-8'), 1)
                                        lib_display.displayString("Pls Wait...     ".encode('utf-8'), 2)

                                        session.query(AMS_Key_Pegs).delete()
                                        session.commit()

                                        for keylistid in ams_can.key_lists:
                                            for slot in range(1,15):
                                                ams_can.set_single_LED_state(keylistid, slot, CAN_LED_STATE_BLINK)
                                                peg_id = None
                                                peg_id = ams_can.get_key_id(keylistid, slot)

                                                if peg_id:
                                                    record = session.query(AMS_Key_Pegs).filter(
                                                        AMS_Key_Pegs.peg_id == peg_id).all()

                                                    key_pos_no = slot + ((keylistid - 1) * 14)

                                                    if record:
                                                        peg_display_msg = ("Key " + str(key_pos_no) + " reg. done").encode('utf-8')
                                                        lib_display.displayString(peg_display_msg, 2)
                                                        sleep(0.5)
                                                    else:
                                                        new_peg_id = AMS_Key_Pegs(peg_id=peg_id,
                                                                                  keylist_no=keylistid,
                                                                                  keyslot_no=slot)
                                                        session.add(new_peg_id)
                                                        session.commit()


                                                        # code added by ravi here
                                                        key = session.query(AMS_Keys).filter((AMS_Keys.keyStrip == int(keylistid)) & (AMS_Keys.keyPosition == int(slot))).one_or_none()
                                                        print(key)
                                                        key.peg_id = peg_id
                                                        session.commit()
                                                        # code added by ravi here


                                                        peg_display_msg = ("Key " + str(key_pos_no) + " reg. done").encode('utf-8')
                                                        lib_display.displayString(peg_display_msg, 2)
                                                        sleep(0.5)
                                                ams_can.set_single_LED_state(keylistid, slot, CAN_LED_STATE_OFF)

                                    # for kgetCardDetailseylistid in ams_can.key_lists:
                                    #     ams_can.lock_all_positions(keylistid)
                                    #     ams_can.set_all_LED_OFF(keylistid)
                                    for keyid in ams_can.key_lists:
                                        ams_can.set_all_LED_ON(keyid, True)
                                        sleep(1)
                                        ams_can.lock_all_positions(keyid)
                                        sleep(1)
                                        ams_can.set_all_LED_OFF(keyid)
                                    ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=None,
                                                                  activityId=None,
                                                                  eventId=EVENT_PEG_REG_DONE,
                                                                  loginType=get_login_type(),
                                                                  access_log_id=None,
                                                                  timeStamp=datetime.now(tz_IN),
                                                                  event_type=EVENT_TYPE_EVENT, is_posted=0)
                                    session.add(ams_event_log)
                                    session.commit()
                                    # lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                                    # ams_can.lib_door_lock.setKeyBoxLock(ams_can.Lock_FD, 1, 1, 0)
                                    # ams_can.door_closed_status = True
                                    lib_display.displayString("WELCOME AMS V1.1".encode('utf-8'), 1)
                                    continue
                                elif key_str == "4":
                                    key_str_4(session, user_auth, ams_access_log, lib_display, lib_keypad, FD_KEYPAD)
                                    continue  # Go back to main loop after date/time set
                                elif key_str == "5":
                                    key_str_5(session, user_auth, ams_access_log, lib_display, lib_keypad, FD_KEYPAD)
                                    continue  # Go back to main loop after network config
                                elif key_str == "F1":
                                    continue
                                else:
                                    lib_display.displayString("                ".encode('utf-8'), 2)
                                    lib_display.displayString("User not admin!".encode('utf-8'), 2)
                                    sleep(2)
                                    continue
                            else:
                                lib_display.displayString("                ".encode('utf-8'), 2)
                                lib_display.displayString("User not admin!".encode('utf-8'), 2)
                                sleep(2)
                                continue
                elif key_str == "F2":
                    is_activity.is_active = 1
                    session.commit()
                    ##########################################################


                    print("############   Step 19  ###########")
                    lib_display.displayString("                ".encode('utf-8'), 2)
                    lib_display.displayString("Admin PIN: ".encode('utf-8'), 2)
                    pin_entered = login_using_PIN(lib_display, lib_keypad, FD_KEYPAD)
                    lib_display.displayString("Validating PIN..".encode('utf-8'), 2)
                    user_auth = dict()
                    if not (pin_entered == ''):
                        if pin_entered == '36943':
                            user_auth = {"ResultCode": AUTH_RESULT_SUCCESS, "id": 1, "name": 'RO-Admin',
                                         "roleId": 1}
                        else:
                            user_auth = {"ResultCode": AUTH_RESULT_FAILED, "id": 0, "name": '',
                                         "roleId": 0}
                        # user_auth = ams_user.get_user_id(session, AUTH_MODE_PIN, pin_no=pin_entered)
                        # print("user Auth : " + str(user_auth))
                        if user_auth["ResultCode"] == AUTH_RESULT_SUCCESS:
                            # Below query not working --
                            # roleName = session.query(ams_cabinet.roles.roleName).filter(ams_cabinet.roles.id
                            #                                                            == user_auth["roleId"]).first()
                            roleId = user_auth["roleId"]
                            if roleId == 1:
                                lib_display.displayString("Take/Return Keys".encode('utf-8'), 2)
                                ams_can.unlock_all_positions(1)
                                ams_can.set_all_LED_ON(1, False)

                                ams_can.unlock_all_positions(2)
                                ams_can.set_all_LED_ON(2, False)
                                lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_UN_LOCK)

                                # ams_can.lib_door_lock.setKeyBoxLock(ams_can.Lock_FD, 1, 1, 1)
                                ams_can.door_closed_status = False

                                print(f"user id is : {user_auth['id']}")

                                
                                ams_access_log = AMS_Access_Log(signInTime=datetime.now(tz_IN), signInMode=get_auth_mode(),
                                                               signInFailed=0, signInSucceed=1,
                                                               signInUserId=user_auth["id"],
                                                               activityCodeEntryTime=datetime.now(tz_IN), activityCode=1,
                                                               doorOpenTime=datetime.now(tz_IN), keysAllowed=None, keysTaken=None,
                                                               keysReturned=None, doorCloseTime=None,
                                                               event_type_id=EVENT_DOOR_OPEN, is_posted=0)
                                session.add(ams_access_log)
                                session.commit()

        
                                ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=None,
                                                              activityId=1,
                                                              eventId=EVENT_EMERGENCY_DOOR_OPEN,
                                                              loginType="Emergency",
                                                              access_log_id=ams_access_log.id,
                                                              timeStamp=datetime.now(tz_IN),
                                                              event_type=EVENT_TYPE_EXCEPTION, is_posted=0)
                                session.add(ams_event_log)
                                session.commit()

                                # Wait till user takes/returns keys and closes the door
                                # Make list of keys taken or keys returned

                




                                ####################################################### following code has been commented by ravi 


                                # sec_counter = 0
                                # door_is_open = False
                                # while True:
                                #     door_status = lib_KeyboxLock.getDoorSensorStatus1()
                                #     sleep(1)
                                #     sec_counter += 1
                                #     if door_status == 0:
                                #         door_is_open = True
                                #         break
                                #     elif door_status == 1:
                                #         door_is_open = False
                                #     get_key_interactions(ams_can, session, cabinet, ams_access_log, user_auth, lib_display, keys_taken_list, keys_returned_list)

                                #     if sec_counter > 60:
                                #         break

                                #########################################################################################################








                                # Save to DB
                                # is_posted added by ravi
                                ########################################################## code addded by ravi

                                keys_taken_list = []
                                keys_returned_list = []
                                door_is_open = True
                                sec_counter = 0
                                while door_is_open:
                                    door_status = lib_KeyboxLock.getDoorSensorStatus1()
                                    print(f'door status is: {door_status}')
                                    sleep(1)
                                    sec_counter += 1
                                    if door_status == 0:
                                        door_is_open = True
                                    elif door_status == 1 and sec_counter >= 5:
                                        door_is_open = False
                                        break
                                
                                    if sec_counter == 5:
                                        print("inside threshold reached status!!!!!!!!!!!!")
                                        lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                                        # ams_can.lib_door_lock.setKeyBoxLock(ams_can.Lock_FD, 1, 1, 0)
                                        ams_can.door_closed_status = True
                                    
                                    get_key_interactions(ams_can, session, cabinet, ams_access_log, user_auth, lib_display, lib_Buzzer, keys_taken_list, keys_returned_list)

                                    if sec_counter > 60:
                                        lib_display.displayClear()
                                        lib_display.displayString("Door opened too ".encode('utf-8'), 1)
                                        lib_display.displayString("long, close door".encode('utf-8'), 2)
                                        lib_Buzzer.setBuzzerOn()
                                        while True:
                                            door_status = lib_KeyboxLock.getDoorSensorStatus1()
                                            if door_status == 1:
                                                break
                                        break
                                
                                lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                                lib_Buzzer.setBuzzerOff()
                                ams_can.lock_all_positions(1)
                                ams_can.set_all_LED_OFF(1)
                                ams_can.lock_all_positions(2)
                                ams_can.set_all_LED_OFF(2)
                                lib_display.displayClear()
                                lib_display.displayString("  Door Closed  ".encode('utf-8'), 2)

                                ams_access_log.keysAllowed = ''
                                ams_access_log.keysTaken = str(keys_taken_list)
                                ams_access_log.keysReturned = str(keys_returned_list)
                                ams_access_log.event_type_id = EVENT_TYPE_EVENT
                                ams_access_log.doorCloseTime = datetime.now(tz_IN)
                                session.commit()
                                ##############################################################################


                                ################################################### code commented by ravi

                                # sec_counter = 0
                                # while door_is_open:
                                #     sec_counter += 1
                                #     sleep(1)
                                #     if sec_counter == 5:
                                #         lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                                #         # ams_can.lib_door_lock.setKeyBoxLock(ams_can.Lock_FD, 1, 1, 0)
                                #         # ams_can.door_closed_status = True
                                #     door_status = lib_KeyboxLock.getDoorSensorStatus1()
                                #     if door_status == 0:
                                #         door_is_open = True
                                #     elif door_status == 1:
                                #         door_is_open = False
                                # ams_can.lock_all_positions(1)
                                # ams_can.set_all_LED_OFF(1)

                                # ams_can.lock_all_positions(2)
                                # ams_can.set_all_LED_OFF(2)

                                # lib_display.displayString("   Close Door   ".encode('utf-8'), 2)
                                # sleep(2)
                                # lib_display.displayClear()
                                # ams_access_log.doorCloseTime = datetime.now(tz_IN)
                                # ams_access_log.event_type_id = EVENT_TYPE_EVENT
                                # session.commit()

                                ##################################################################################################


                                ams_event_log = AMS_Event_Log(userId=user_auth["id"], keyId=None,
                                                              activityId=1,
                                                              eventId=EVENT_DOOR_CLOSED,
                                                              loginType=get_login_type(),
                                                              access_log_id=ams_access_log.id,
                                                              timeStamp=datetime.now(tz_IN),
                                                              event_type=EVENT_TYPE_EVENT, is_posted=0)
                                session.add(ams_event_log)
                                session.commit()
              
              
                                continue


            # except KeyboardInterrupt:
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
        lib_display.displayString("AMS not active! ", 2)
        session.close()
        return


if __name__ == "__main__":
    main()