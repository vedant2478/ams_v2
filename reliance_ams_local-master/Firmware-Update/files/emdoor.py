#  file updated as per date 16th Frb 2023

import requests
import time
import ast
import json
import schedule
import ctypes
from time import sleep
from datetime import datetime, timedelta
import pytz
from model import *
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import date, datetime, timedelta
from threading import Lock
from amscan import *

AUTH_MODE_PIN = 1
AUTH_MODE_CARD_PIN = 2
AUTH_MODE_BIO = 3
AUTH_MODE_WEB = 4

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

EVENT_TYPE_EVENT = 1
EVENT_TYPE_ALARM = 2

SLOT_STATUS_KEY_NOT_PRESENT = 0
SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT = 1
SLOT_STATUS_KEY_PRESENT_WRONG_SLOT = 2

BATTERY_CHARGE_PC = None

MAIN_DOOR_LOCK = 0
MAIN_DOOR_UN_LOCK = 1


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

TZ_INDIA = pytz.timezone("Asia/Kolkata")
LAST_ACK_TIME = datetime.now(TZ_INDIA)
ACK_COUNTER = 0


def ams_header_line(session, lib_battery):
    ams_alarm_count = (
        session.query(AMS_Event_Log).filter(AMS_Event_Log.event_type == 2).count()
    )
    # print("Alarm Count = " + str(ams_alarm_count))
    bcp = lib_battery.getBatteryPercentage()
    ams_header_line_str = "Alarm " + str(ams_alarm_count) + " Bat " + str(bcp) + "%"
    return ams_header_line_str


def update_keys_status(ams_can, list_ID, session):

    for key_num in range(1, 15):
        key_id = ams_can.get_key_id(list_ID, key_num)
        # print("Key Id : " + str(key_id))
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


def get_key_interactions(
    ams_can2,
    session,
    cabinet,
    ams_access_log,
    user_auth,
    lib_display,
    keys_taken_list,
    keys_returned_list,
):
    key_record = None
    # lib_display.displayInit()
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
                    "keyTakenBy": user_auth.id,
                    "keyTakenByUser": user_auth.name,
                    "current_pos_strip_id": ams_can2.key_taken_position_list,
                    "current_pos_slot_no": ams_can2.key_taken_position_slot,
                    "keyTakenAtTime": datetime.now(TZ_INDIA),
                    "keyStatus": SLOT_STATUS_KEY_NOT_PRESENT,
                }
            )
            session.commit()

            # is_posted added by ravi
            ams_event_log = AMS_Event_Log(
                userId=user_auth.id,
                keyId=key_record.id,
                activityId=None,
                eventId=EVENT_KEY_TAKEN_CORRECT,
                loginType="WEB",
                access_log_id=ams_access_log.id,
                timeStamp=datetime.now(TZ_INDIA),
                event_type=EVENT_TYPE_ALARM,
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
        ams_can2.key_taken_event = False

    elif ams_can2.key_inserted_event:
        print("############   key has been inserted  ###########")
        print("\n\nKEY INSERTED\n\n")
        for key in cabinet.keys:
            if key.peg_id == ams_can2.key_inserted_id:
                key_record = key

        print(
            key_record.keyStrip,
            ams_can2.key_inserted_position_list,
            ams_can2.key_inserted_position_slot,
        )
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

                # is_posted added by ravi
                ams_event_log = AMS_Event_Log(
                    userId=user_auth.id,
                    keyId=key_record.id,
                    activityId=None,
                    eventId=EVENT_KEY_RETURNED_RIGHT_SLOT,
                    loginType="WEB",
                    access_log_id=ams_access_log.id,
                    timeStamp=datetime.now(TZ_INDIA),
                    event_type=EVENT_TYPE_ALARM,
                    is_posted=0,
                )
                session.add(ams_event_log)
                session.commit()
                lib_display.displayClear()
                lib_display.displayString(keys_msg_print, 2)
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

                # is_posted added by ravi
                ams_event_log = AMS_Event_Log(
                    userId=user_auth.id,
                    keyId=key_record.id,
                    activityId=None,
                    eventId=EVENT_KEY_RETURNED_WRONG_SLOT,
                    loginType="WEB",
                    access_log_id=ams_access_log.id,
                    timeStamp=datetime.now(TZ_INDIA),
                    event_type=EVENT_TYPE_ALARM,
                    is_posted=0,
                )
                session.add(ams_event_log)
                session.commit()
                lib_display.displayClear()
                lib_display.displayString(keys_msg_print, 2)

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
                    lib_display.displayString(msg_line1, 1)
                    lib_display.displayString(msg_line2, 2)

                    if key_record.id not in keys_returned_list:
                        keys_returned_list.append(key_record.id)
                    if key_record.id in keys_taken_list:
                        keys_taken_list.remove(key_record.id)
                else:
                    msg_line1 = "Key in wrong pos".encode("utf-8")
                    msg_line2 = "Correct pos n/a ".encode("utf-8")
                    lib_display.displayClear()
                    lib_display.displayString(msg_line1, 1)
                    lib_display.displayString(msg_line2, 2)

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
            lib_display.displayClear()
            lib_display.displayString(msg_line1, 1)
            lib_display.displayString(msg_line2, 2)
            sleep(1)


def get_emergenecy_door_status(
    lib_display,
    FD_KEYPAD,
    ams_can2,
    session,
    lib_KeyboxLock,
    cabinet,
    lib_Buzzer,
    lib_battery,
):
    print(
        "################### inside get emergency door status #########################"
    )

    is_activity = (
        session.query(AMS_Activity_Progress_Status)
        .filter(AMS_Activity_Progress_Status.id == 1)
        .one_or_none()
    )
    if is_activity.is_active:
        return

    mutex.acquire()

    ams_emergency_req = AMS_emergency_door_open()
    ams_access_log = None
    keys_taken_list = []
    keys_returned_list = []
    print("\n** 3")
    try:
        print("\n** 4")
        rec_emg = ams_emergency_req.is_emergency_req_received(session)

        if rec_emg == None:
            print("no emergency record found!")
        else:
            print(
                "############################################################################################"
            )
            if rec_emg.emergency_status == 1:

                print("\n** 6")

                user_auth = (
                    session.query(AMS_Users)
                    .filter(AMS_Users.id == rec_emg.userId)
                    .one_or_none()
                )
                print(f"user name is : {user_auth.name}")

                ams_access_log = AMS_Access_Log(
                    signInTime=datetime.now(TZ_INDIA),
                    signInMode=AUTH_MODE_WEB,
                    signInFailed=0,
                    signInSucceed=1,
                    signInUserId=user_auth.id,
                    activityCodeEntryTime=None,
                    activityCode=None,
                    doorOpenTime=None,
                    keysAllowed=None,
                    keysTaken=None,
                    keysReturned=None,
                    doorCloseTime=None,
                    event_type_id=EVENT_EMERGENCY_DOOR_OPEN,
                    is_posted=0,
                )
                session.add(ams_access_log)
                session.commit()

                lib_display.displayClear()
                lib_display.displayString("Emergency req. ".encode("utf-8"), 1)
                lib_display.displayString("Opening door ".encode("utf-8"), 2)
                sleep(1)
                ams_can2.lib_door_lock.setKeyBoxLock(ams_can2.Lock_FD, 1, 1, 1)
                lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_UN_LOCK)
                ams_can2.unlock_all_positions(1)
                ams_can2.set_all_LED_ON(1, False)
                ams_can2.unlock_all_positions(2)
                ams_can2.set_all_LED_ON(2, False)
                ams_can2.door_closed_status = False
                # Save to DB
                ams_access_log.doorOpenTime = datetime.now(TZ_INDIA)
                ams_access_log.event_type_id = EVENT_TYPE_ALARM
                ams_access_log.signInUserId = rec_emg.userId

                # is_posted added by ravi
                ams_event_log = AMS_Event_Log(
                    userId=rec_emg.userId,
                    keyId=None,
                    activityId=None,
                    eventId=EVENT_EMERGENCY_DOOR_OPEN,
                    loginType="WEB",
                    access_log_id=ams_access_log.id,
                    timeStamp=datetime.now(TZ_INDIA),
                    event_type=EVENT_TYPE_ALARM,
                    is_posted=0,
                )
                session.add(ams_event_log)
                session.commit()

                sec_counter = 0
                door_is_open = True

                ams_can2.cleanup()
                sleep(2)

                while door_is_open:
                    print("\n** 7")
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
                        print("inside threshold reached status!!!!!!!!!!!!")
                        lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                        ams_can2.lib_door_lock.setKeyBoxLock(ams_can.Lock_FD, 1, 1, 0)
                        ams_can2.door_closed_status = True

                    get_key_interactions(
                        ams_can2,
                        session,
                        cabinet,
                        ams_access_log,
                        user_auth,
                        lib_display,
                        keys_taken_list,
                        keys_returned_list,
                    )

                    if sec_counter > 60:
                        lib_display.displayClear()
                        lib_display.displayString("Door opened too ".encode("utf-8"), 1)
                        lib_display.displayString("long, close door".encode("utf-8"), 2)
                        lib_Buzzer.setBuzzerOn()
                        while True:
                            door_status = lib_KeyboxLock.getDoorSensorStatus1()
                            if door_status == 1:
                                break
                        break

                lib_KeyboxLock.setKeyBoxLock(MAIN_DOOR_LOCK)
                lib_Buzzer.setBuzzerOff()
                ams_can2.lock_all_positions(1)
                ams_can2.set_all_LED_OFF(1)
                ams_can2.lock_all_positions(2)
                ams_can2.set_all_LED_OFF(2)
                lib_display.displayClear()
                lib_display.displayString("  Door Closed  ".encode("utf-8"), 2)

                ams_access_log.doorCloseTime = datetime.now(TZ_INDIA)
                ams_access_log.keysAllowed = ""
                ams_access_log.keysTaken = str(keys_taken_list)
                ams_access_log.keysReturned = str(keys_returned_list)
                ams_access_log.event_type_id = EVENT_TYPE_ALARM
                session.commit()

                # is_posted added by ravi
                ams_event_log = AMS_Event_Log(
                    userId=user_auth.id,
                    keyId=None,
                    activityId=None,
                    eventId=EVENT_DOOR_CLOSED,
                    loginType="WEB",
                    access_log_id=ams_access_log.id,
                    timeStamp=datetime.now(TZ_INDIA),
                    event_type=EVENT_TYPE_ALARM,
                    is_posted=0,
                )
                session.add(ams_event_log)
                session.commit()
                header_line = ams_header_line(session, lib_battery)
                lib_display.displayClear()
                lib_display.displayString(header_line.encode("utf-8"), 1)
                login_msg = (
                    "Site: "
                    + cabinet.site.siteName
                    + (" " * int(10 - len(cabinet.site.siteName)))
                )

                # if not pegs_verified:
                lib_display.displayString("Please wait...  ".encode("utf-8"), 2)
                for lists in ams_can2.key_lists:
                    update_keys_status(ams_can2, lists, session)
                lib_display.displayString(login_msg.encode("utf-8"), 2)
        mutex.release()
        return
    except Exception as e:
        print(e.__traceback__)
        mutex.release()
        return


def get_key_taken_too_long_status(
    ams_can,
    session,
    lib_battery,
    lib_display,
    lib_Buzzer,
    lib_keypad,
    FD_KEYPAD,
    cabinet,
):

    global TZ_INDIA
    global ACK_COUNTER
    global LAST_ACK_TIME

    print("############### inside key taken for too long status ###################")

    is_activity = (
        session.query(AMS_Activity_Progress_Status)
        .filter(AMS_Activity_Progress_Status.id == 1)
        .one_or_none()
    )
    if is_activity.is_active:
        return
    try:
        mutex.acquire()
        keys_taken = session.query(AMS_Keys).filter(AMS_Keys.keyStatus == 0).all()
        keys_taken_list_with_time = []
        is_limit_reached = []
        current_time = datetime.now(TZ_INDIA)
        print(f"current time is: {current_time}")
        if keys_taken != []:
            keys_taken_list_with_time = [
                (key.keyName, key.keyTakenAtTime.astimezone(TZ_INDIA))
                if key.keyTakenAtTime != None
                else current_time
                for key in keys_taken
            ]
            keys_taken_list = [key.keyName for key in keys_taken]
            print(keys_taken_list_with_time)

            ############################################################### process to calculate time limit for the key taken based on activity
            past_dt = current_time + timedelta(days=-3)
            access_logs = (
                session.query(AMS_Access_Log)
                .filter(
                    (AMS_Access_Log.activityCode != None)
                    & (AMS_Access_Log.keysTaken != "[]")
                    & (AMS_Access_Log.doorCloseTime > past_dt)
                )
                .all()
            )

            times = []
            if access_logs != None:
                access_logs_filtered = []
                for acl in access_logs:
                    keys = ast.literal_eval(acl.keysTaken)
                    for key in keys:
                        if key in keys_taken_list:
                            access_logs_filtered.append(acl)
                            break

                activity_codes = [acl.activityCode for acl in access_logs_filtered]
                print(activity_codes)
                final_activity_codes = list(set(activity_codes))
                print(final_activity_codes)
                time_limits = []
                for code in final_activity_codes:
                    activity = (
                        session.query(AMS_Activities)
                        .filter(AMS_Activities.activityCode == code)
                        .one_or_none()
                    )
                    if activity:
                        time_limits.append(activity)
                times = [act.timeLimit for act in time_limits]
                if times == []:
                    times.append(60)
                print(times)
            else:
                print("no record found")
                times.append(60)
                print(times)

            for key in keys_taken_list_with_time:
                try:
                    key_taken_time = key[1]
                    print(
                        f"################################# key taken time: {key_taken_time} #############################"
                    )
                    print(
                        f"Number of minutes: {(current_time - key_taken_time).total_seconds() // 60}"
                    )
                    print(ACK_COUNTER)
                    if ((current_time - key_taken_time).total_seconds() // 60) >= min(
                        times
                    ):
                        is_limit_reached.append(key)
                    if ACK_COUNTER != 0:
                        is_limit_reached.append(key)
                except Exception as e:
                    print("exception occured in key data collection.")
                    continue

        else:
            ACK_COUNTER = 0
            mutex.release()
            return

        key_took_at = None
        if is_limit_reached != []:
            print(f"following keys have reached their limits: {is_limit_reached}")
            key_took_at = min([key[1] for key in is_limit_reached])
            if ACK_COUNTER == 0:
                LAST_ACK_TIME = key_took_at
        else:
            print("no key has reached limit!")

        print(f"last acknowledgement: {LAST_ACK_TIME}")
        # current_time = datetime.now(TZ_INDIA)
        time_diff = current_time - LAST_ACK_TIME
        # print(f'time diff: {time_diff}')
        if time_diff.total_seconds() // 60 >= 10 and key_took_at != None:
            if len(keys_taken_list_with_time) > 0:

                lib_display.displayClear()
                lib_display.displayString(
                    f'{len(keys_taken_list_with_time)} {"Key" if len(keys_taken_list_with_time)==1 else "keys"} Out'.encode(
                        "utf-8"
                    ),
                    1,
                )
                lib_display.displayString("Press 1 For ACK.".encode("utf-8"), 2)
                lib_Buzzer.setBuzzerOn()
                print(
                    "##############################################\nBuzzer is on\n################################################"
                )
                key_str = ""
                FD_KEYPAD = lib_keypad.keypadInit()
                key = lib_keypad.keypadHandler(FD_KEYPAD)
                key_str = str(KEY_DICT[str(key)])
                if key_str == "1":
                    LAST_ACK_TIME = datetime.now(TZ_INDIA)
                    ACK_COUNTER += 1
                    lib_Buzzer.setBuzzerOff()
                    sleep(1)
                    header_line = ams_header_line(session, lib_battery)
                    lib_display.displayClear()
                    lib_display.displayString(header_line.encode("utf-8"), 1)
                    login_msg = (
                        "Site: "
                        + cabinet.site.siteName
                        + (" " * int(10 - len(cabinet.site.siteName)))
                    )

                    # if not pegs_verified:
                    lib_display.displayString("Please wait...  ".encode("utf-8"), 2)
                    for lists in ams_can.key_lists:
                        update_keys_status(ams_can, lists, session)
                    lib_display.displayString(login_msg.encode("utf-8"), 2)
    except Exception as e:
        print(e)
    mutex.release()
    return


if __name__ == "__main__":

    lib_battery = ctypes.CDLL("libBattery.so")
    lib_battery.getBatteryPercentage.argtypes = []
    lib_battery.bmsInit.argtypes = []
    lib_battery.getCardDetails.argtypes = []
    lib_battery.getCardDetails.restype = ctypes.c_ulonglong

    lib_KeyboxLock = ctypes.CDLL("libKeyboxLock.so")
    lib_KeyboxLock.getDoorSensorStatus1.argtypes = []
    lib_KeyboxLock.setKeyBoxLock.argtypes = [ctypes.c_int]
    lib_KeyboxLock.getDoorSensorStatus1.argtypes = []

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

    lib_Buzzer = ctypes.CDLL("libBuzzer.so")
    lib_Buzzer.setBuzzerOn.argtypes = []
    lib_Buzzer.setBuzzerOff.argtypes = []

    lib_keypad = ctypes.CDLL("libKeypad.so")
    lib_keypad.keypadInit.argtypes = []
    lib_keypad.keypadHandler.argtypes = [ctypes.c_int]
    lib_keypad.keypadClose.argtypes = [ctypes.c_int]
    FD_KEYPAD = lib_keypad.keypadInit()

    SQLALCHEMY_DATABASE_URI = "sqlite:////home/ams-core/csiams.dev.sqlite"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URI, connect_args={"check_same_thread": False}
    )
    Session = sessionmaker()
    Session.configure(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    mutex = Lock()
    cabinet = session.query(AMS_Cabinet).one_or_none()
    ams_can = AMS_CAN()
    ams_can2 = AMS_CAN()

    schedule.every(10).seconds.do(
        get_emergenecy_door_status,
        lib_display,
        FD_KEYPAD,
        ams_can2,
        session,
        lib_KeyboxLock,
        cabinet,
        lib_Buzzer,
        lib_battery,
    )
    schedule.every(15).seconds.do(
        get_key_taken_too_long_status,
        ams_can,
        session,
        lib_battery,
        lib_display,
        lib_Buzzer,
        lib_keypad,
        FD_KEYPAD,
        cabinet,
    )

    while True:
        try:
            schedule.run_pending()
            sleep(1)
        except Exception as e:
            print(e)
