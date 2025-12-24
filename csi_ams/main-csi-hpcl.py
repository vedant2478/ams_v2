import os
import mraa
import pytz
from model import *
from amscan import *
from time import sleep
from utils.commons import *
from datetime import datetime
from utils import lcd
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref, sessionmaker
from sqlalchemy import Column, Integer, String, ForeignKey, Table, create_engine


BUZZ.write(1)
sleep(4)
BUZZ.write(0)

lcd.lcd_init()

lcd.lcd_string("POWERED BY CSI", lcd.LCD_LINE_1)
sleep(2)

print("Bring up CAN0....")
os.system("sudo ip link set can0 down")
sleep(3)
os.system("sudo ip link set can0 up type can bitrate 125000")
sleep(2)


counter = 0


def main():
    TZ_INDIA = pytz.timezone("Asia/Kolkata")
    IS_KEY_IN_WRONG_SLOT = None
    IS_KEY_IN_WRONG_SLOT_Correct_Strip = None
    IS_KEY_IN_WRONG_SLOT_Correct_Pos = None
    IS_KEY_IN_WRONG_SLOT_Wrong_Strip = None
    IS_KEY_IN_WRONG_SLOT_Wrong_Pos = None

    current_date = datetime.now(TZ_INDIA).strftime("%d-%m-%Y %H:%M")

    try:
        engine = create_engine(SQLALCHEMY_DATABASE_URI)
        Session = sessionmaker()
        Session.configure(bind=engine)
        session = Session()
    except Exception as e:
        print("%" * 100)
        print(e)

    is_activity = (
        session.query(AMS_Activity_Progress_Status)
        .filter(AMS_Activity_Progress_Status.id == 1)
        .first()
    )

    if is_activity.is_active == CABINET_SHUTDOWN_INT:
        lcd.clear_display()
        lcd.lcd_string(f"DEVICE INACTIVE", lcd.LCD_LINE_1)
        sleep(2)
        return

    ams_cabinet = AMS_Cabinet()
    ams_event_types = AMS_Event_Types()
    ams_event_logs = AMS_Event_Log()
    ams_access_log = None
    ams_event_log = None
    ams_user = AMS_Users()
    ams_can = None
    ams_alarm_count = 0
    BATTERY_CHARGE_PC = str(bms.get_batt_pct(bms.ser))

    cabinet = session.query(AMS_Cabinet).first()

    if cabinet:
        lcd.lcd_string(f"HPCL KMS    {BATTERY_CHARGE_PC}%", lcd.LCD_LINE_1)
        lcd.lcd_string(current_date, lcd.LCD_LINE_2)
        sleep(2)

        ams_can = AMS_CAN()
        ams_can.get_version_number(1)
        ams_can.get_version_number(2)
        sleep(2)

        ams_can = AMS_CAN()
        sleep(6)
        ams_can.get_version_number(1)
        ams_can.get_version_number(2)

        print("\nNo of key-lists : " + str(len(ams_can.key_lists)))

        for keys in ams_can.key_lists:
            print("Key-list Id : " + str(keys))

        show_ideal_msg(lcd, cabinet)

        for keylistid in ams_can.key_lists:
            ams_can.unlock_all_positions(keylistid)
            ams_can.set_all_LED_OFF(keylistid)

        pegs_verified = False
        is_activity = (
            session.query(AMS_Activity_Progress_Status)
            .filter(AMS_Activity_Progress_Status.id == 1)
            .first()
        )

        flag = False

        while True:
            print("############   Step 1  ###########")
            try:

                if is_activity.is_active == CABINET_SHUTDOWN_INT:
                    lcd.clear_display()
                    lcd.lcd_string(f"DEVICE INACTIVE", lcd.LCD_LINE_1)
                    sleep(2)
                    return

                show_ideal_msg(lcd, cabinet)

                lcd.lcd_string("Please wait...  ", lcd.LCD_LINE_2)
                sleep(2)
                for lists in ams_can.key_lists:
                    update_keys_status(ams_can, lists, session)

                pegs_verified = True
                if not flag:
                    is_activity.is_active = 0
                    session.commit()

                show_ideal_msg(lcd, cabinet)

                key_str = take_key_pad_input(session, key_pad)
                is_activity = (
                    session.query(AMS_Activity_Progress_Status)
                    .filter(AMS_Activity_Progress_Status.id == 1)
                    .first()
                )

                if is_activity.is_active == 1:
                    flag = True
                    lcd.clear_display()
                    lcd.lcd_string("ACK. PENDING", lcd.LCD_LINE_1)
                    lcd.lcd_string("Press 1 for ACK.", lcd.LCD_LINE_2)
                    key_str = take_key_pad_input(session, key_pad)
                    if key_str != 1:
                        continue

                if is_activity.is_active == CABINET_SHUTDOWN_INT:
                    lcd.clear_display()
                    lcd.lcd_string(f"DEVICE INACTIVE", lcd.LCD_LINE_1)
                    sleep(2)
                    return

                flag = False

                pin_entered = None
                user_auth = None

                # functionality to check ip address -- just for testing purpose
                try:
                    if key_str == "5":
                        lcd.clear_display()

                        ips = os.popen("hostname -I").read().split()
                        if len(ips) > 1:
                            ip_addr_eth0 = ips[0]
                            ip_addr_static = ips[1]
                            lcd.lcd_string(ip_addr_eth0, lcd.LCD_LINE_1)
                            lcd.lcd_string(ip_addr_static, lcd.LCD_LINE_2)
                            sleep(3)
                        else:
                            lcd.lcd_string(ips[0], lcd.LCD_LINE_1)
                            sleep(3)
                except Exception as e:
                    print(e)

                if key_str == "#":

                    is_activity.is_active = 2
                    session.commit()

                    print("############   Step 2  ###########")
                    try:
                        auth_mode, valid_data = login_using_PIN_Card(
                            lcd, key_pad, session=session
                        )
                        final_auth_mode = None
                        final_signin_mode = None

                        if auth_mode == -1:
                            continue
                        elif auth_mode == 2:
                            final_auth_mode = auth_mode
                            final_signin_mode = "CARD"
                            card_swiped = valid_data
                            print(
                                "Auth mode :"
                                + str(auth_mode)
                                + " card no : "
                                + str(card_swiped)
                            )
                            user_auth = ams_user.get_user_id(
                                session, auth_mode, card_no=card_swiped
                            )
                        elif auth_mode == 1:
                            final_auth_mode = auth_mode
                            final_signin_mode = "PIN"
                            pin_no = valid_data
                            pin_entered = pin_no
                            print(
                                "Auth mode :"
                                + str(auth_mode)
                                + " pin no : "
                                + str(pin_no)
                            )
                            user_auth = ams_user.get_user_id(
                                session, auth_mode, pin_no=pin_no
                            )
                        else:
                            continue

                        if user_auth["ResultCode"] == AUTH_RESULT_SUCCESS:
                            print("############   Step 3  ###########")
                            lcd.clear_display()
                            sleep(1)
                            lcd.lcd_string("SIGN IN Success", lcd.LCD_LINE_1)
                            user_str = ("User: " + (user_auth["name"])[0:12]).ljust(
                                15, " "
                            )
                            lcd.lcd_string(user_str, lcd.LCD_LINE_2)
                            sleep(2)
                            ams_access_log = AMS_Access_Log(
                                signInTime=datetime.now(TZ_INDIA),
                                signInMode=final_auth_mode,
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

                            eventDesc = get_event_description(
                                session, EVENT_LOGIN_SUCCEES
                            )

                            ams_event_log = AMS_Event_Log(
                                userId=user_auth["id"],
                                keyId=None,
                                activityId=None,
                                eventId=EVENT_LOGIN_SUCCEES,
                                loginType=final_signin_mode,
                                access_log_id=ams_access_log.id,
                                timeStamp=datetime.now(TZ_INDIA),
                                event_type=EVENT_TYPE_EVENT,
                                eventDesc=eventDesc,
                                is_posted=0,
                            )
                            session.add(ams_event_log)
                            session.commit()
                        else:
                            user_str = str(user_auth["Message"]).ljust(16, " ")
                            lcd.lcd_string(user_str, lcd.LCD_LINE_2)
                            sleep(3)
                            ams_access_log = AMS_Access_Log(
                                signInTime=datetime.now(TZ_INDIA),
                                signInMode=final_auth_mode,
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

                            eventDesc = get_event_description(
                                session, EVENT_LOGIN_FAILED
                            )

                            ams_event_log = AMS_Event_Log(
                                userId=0,
                                keyId=None,
                                activityId=None,
                                eventId=EVENT_LOGIN_FAILED,
                                loginType=final_signin_mode,
                                access_log_id=ams_access_log.id,
                                timeStamp=datetime.now(TZ_INDIA),
                                event_type=EVENT_TYPE_ALARM,
                                eventDesc=eventDesc,
                                is_posted=0,
                            )
                            session.add(ams_event_log)
                            session.commit()
                            continue

                        if user_auth["ResultCode"] == AUTH_RESULT_SUCCESS:
                            print("############   Step 4  ###########")
                            try:
                                print("############   Step 5  ###########")
                                lcd.clear_display()
                                sleep(1)
                                lcd.lcd_string("Enter ACT Code", lcd.LCD_LINE_1)
                                act_code_entered = get_activity_code(
                                    session, lcd, key_pad
                                )
                                print(act_code_entered)
                                ams_activities = AMS_Activities()
                                dic_result = ams_activities.get_keys_allowed(
                                    session,
                                    user_auth["id"],
                                    act_code_entered,
                                    datetime.now(TZ_INDIA),
                                )

                                if dic_result["ResultCode"] == ACTIVITY_ALLOWED:
                                    print("############   Step 6  ###########")

                                    lcd.lcd_string(
                                        dic_result["Description"][:16], lcd.LCD_LINE_1
                                    )
                                    lcd.lcd_string(
                                        dic_result["Description"][16:], lcd.LCD_LINE_2
                                    )
                                    sleep(1)
                                    lcd.clear_display()

                                    allowed_keys_list = None
                                    allowed_keys_list = (
                                        dic_result["Message"].strip("][").split(",")
                                    )
                                    print(
                                        "\nAllowed Keys are : " + str(allowed_keys_list)
                                    )
                                    lcd.clear_display()

                                    lcd.lcd_string("Allowed Keys", lcd.LCD_LINE_1)
                                    lcd.lcd_string(
                                        str(allowed_keys_list)
                                        .strip("][")
                                        .replace("'", "")
                                        .replace("'", "")
                                        .replace(" ", ""),
                                        lcd.LCD_LINE_2,
                                    )
                                    sleep(2)

                                    ams_access_log.activityCodeEntryTime = datetime.now(
                                        TZ_INDIA
                                    )
                                    ams_access_log.activityCode = act_code_entered
                                    ams_access_log.event_type_id = EVENT_TYPE_EVENT
                                    session.commit()

                                    eventDesc = get_event_description(
                                        session, EVENT_ACTIVITY_CODE_CORRECT
                                    )

                                    ams_event_log = AMS_Event_Log(
                                        userId=user_auth["id"],
                                        keyId=None,
                                        activityId=act_code_entered,
                                        eventId=EVENT_ACTIVITY_CODE_CORRECT,
                                        loginType=final_signin_mode,
                                        access_log_id=ams_access_log.id,
                                        timeStamp=datetime.now(TZ_INDIA),
                                        event_type=EVENT_TYPE_EVENT,
                                        eventDesc=eventDesc,
                                        is_posted=0,
                                    )
                                    session.add(ams_event_log)
                                    session.commit()

                                    keys_OUT_STATUS_list = []
                                    keys_IN_STATUS_List = []
                                    keys_msg_In = "[IN:"
                                    keys_msg_Out = "[OUT:"
                                    key_record_list = []

                                    print("Keys allowed: " + str(allowed_keys_list))
                                    print("Cabinet Keys: " + str(len(cabinet.keys)))

                                    ams_can.lock_all_positions(1)
                                    ams_can.lock_all_positions(2)

                                    for keys in allowed_keys_list:
                                        try:
                                            print("############   Step 7  ###########")
                                            key_record = None
                                            key_slot_no = 0
                                            for key_rec in cabinet.keys:
                                                try:
                                                    print(
                                                        "key_rec.id " + str(key_rec.id)
                                                    )
                                                    print("keys " + str(keys))

                                                    if str(key_rec.id) == str(keys):
                                                        key_record = key_rec
                                                        print(key_record.keyStatus)

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
                                                except Exception as e:
                                                    print(e)
                                        except Exception as e:
                                            print(e)

                                    print("############   Step 8  ###########")
                                    keys_msg_In = keys_msg_In + "]"
                                    keys_msg_Out = keys_msg_Out + "]"
                                    msg_line_1 = (keys_msg_In + keys_msg_Out)[:16]
                                    msg_line_2 = (keys_msg_In + keys_msg_Out)[16:]
                                    lcd.clear_display()

                                    lcd.lcd_string(msg_line_1, lcd.LCD_LINE_1)
                                    lcd.lcd_string(msg_line_2, lcd.LCD_LINE_2)

                                    DOOR_LOCK.write(1)
                                    ams_access_log.doorOpenTime = datetime.now(TZ_INDIA)
                                    ams_access_log.event_type_id = EVENT_TYPE_EVENT
                                    session.commit()

                                    eventDesc = get_event_description(
                                        session, EVENT_DOOR_OPEN
                                    )

                                    ams_event_log = AMS_Event_Log(
                                        userId=user_auth["id"],
                                        keyId=None,
                                        activityId=act_code_entered,
                                        eventId=EVENT_DOOR_OPEN,
                                        loginType=final_signin_mode,
                                        access_log_id=ams_access_log.id,
                                        timeStamp=datetime.now(TZ_INDIA),
                                        event_type=EVENT_TYPE_EVENT,
                                        eventDesc=eventDesc,
                                        is_posted=0,
                                    )
                                    session.add(ams_event_log)
                                    session.commit()

                                    sec_counter = 0
                                    door_is_open = False
                                    while True:
                                        print("############   Step 9  ###########")
                                        door_status = read_limit_switch(LIMIT_SWITCH)
                                        sleep(1)
                                        sec_counter += 1
                                        if door_status == 1:
                                            door_is_open = True
                                            break
                                        elif door_status == 0 and sec_counter >= 5:
                                            door_is_open = False
                                            DOOR_LOCK.write(0)
                                        if sec_counter > 10:
                                            door_is_open = True
                                            break

                                    sec_counter = 0
                                    keys_taken_list = []
                                    keys_returned_list = []
                                    timer = 0
                                    while door_is_open:
                                        print("############   Step 10  ###########")
                                        sleep(0.2)
                                        sec_counter += 1
                                        key_record = None
                                        pin_entered = None

                                        if sec_counter == 25:
                                            DOOR_LOCK.write(0)
                                        elif sec_counter >= 300:
                                            lcd.clear_display()

                                            lcd.lcd_string(
                                                "Door opened too ", lcd.LCD_LINE_1
                                            )
                                            lcd.lcd_string(
                                                "long close door", lcd.LCD_LINE_2
                                            )
                                            BUZZ.write(1)

                                        if ams_can.key_taken_event:
                                            timer = 0
                                            print("############   Step 11  ###########")
                                            print("\n\nKEY TAKEN\n\n")

                                            for key in cabinet.keys:
                                                if key.peg_id == ams_can.key_taken_id:
                                                    key_record = key
                                                    break

                                            if key_record:
                                                keys_msg_print = "Key taken:" + (
                                                    key_record.keyName.ljust(4, " ")
                                                )
                                                print(keys_msg_print)

                                                session.query(AMS_Keys).filter(
                                                    AMS_Keys.peg_id
                                                    == ams_can.key_taken_id
                                                ).update(
                                                    {
                                                        "keyTakenBy": user_auth["id"],
                                                        "keyTakenByUser": user_auth[
                                                            "name"
                                                        ],
                                                        "current_pos_strip_id": None,
                                                        "current_pos_slot_no": None,
                                                        "keyTakenAtTime": datetime.now(
                                                            TZ_INDIA
                                                        ),
                                                        "keyStatus": SLOT_STATUS_KEY_NOT_PRESENT,
                                                        "color": "White",
                                                    }
                                                )
                                                session.commit()

                                                eventDesc = get_event_description(
                                                    session, EVENT_KEY_TAKEN_CORRECT
                                                )

                                                ams_event_log = AMS_Event_Log(
                                                    userId=user_auth["id"],
                                                    keyId=key_record.id,
                                                    activityId=act_code_entered,
                                                    eventId=EVENT_KEY_TAKEN_CORRECT,
                                                    loginType=final_signin_mode,
                                                    access_log_id=ams_access_log.id,
                                                    timeStamp=datetime.now(TZ_INDIA),
                                                    event_type=EVENT_TYPE_EVENT,
                                                    eventDesc=eventDesc,
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
                                                keys_msg_print = "Key not reg.    "

                                            lcd.clear_display()
                                            lcd.lcd_string(
                                                keys_msg_print, lcd.LCD_LINE_2
                                            )
                                            sleep(0.2)
                                            ams_can.key_taken_event = False

                                        elif ams_can.key_inserted_event:
                                            timer = 0
                                            print("############   Step 12  ###########")
                                            print("\n\nKEY INSERTED\n\n")
                                            for key in cabinet.keys:
                                                if (
                                                    key.peg_id
                                                    == ams_can.key_inserted_id
                                                ):
                                                    key_record = key
                                                    break

                                            if key_record:
                                                print(
                                                    "\nKEY INSERTED EVENT - Key Record Found!!!\n"
                                                )
                                                if (
                                                    key_record.keyStrip
                                                    == ams_can.key_inserted_position_list
                                                    and key_record.keyPosition
                                                    == ams_can.key_inserted_position_slot
                                                ):
                                                    print(
                                                        "\nKEY INSERTED EVENT - Key in CORRECT SLOT!!!\n"
                                                    )
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

                                                    ams_can.set_single_LED_state(
                                                        ams_can.key_inserted_position_list,
                                                        ams_can.key_inserted_position_slot,
                                                        CAN_LED_STATE_OFF,
                                                    )
                                                    keys_msg_print = "Key ret:" + (
                                                        key_record.keyName.ljust(4, " ")
                                                    )
                                                    lcd.clear_display()
                                                    lcd.lcd_string(
                                                        keys_msg_print, lcd.LCD_LINE_2
                                                    )

                                                    eventDesc = get_event_description(
                                                        session,
                                                        EVENT_KEY_RETURNED_RIGHT_SLOT,
                                                    )

                                                    ams_event_log = AMS_Event_Log(
                                                        userId=user_auth["id"],
                                                        keyId=key_record.id,
                                                        activityId=act_code_entered,
                                                        eventId=EVENT_KEY_RETURNED_RIGHT_SLOT,
                                                        loginType=final_signin_mode,
                                                        access_log_id=ams_access_log.id,
                                                        timeStamp=datetime.now(
                                                            TZ_INDIA
                                                        ),
                                                        event_type=EVENT_TYPE_EVENT,
                                                        eventDesc=eventDesc,
                                                        is_posted=0,
                                                    )
                                                    session.add(ams_event_log)
                                                    session.commit()
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
                                                    print(
                                                        "\nKEY INSERTED - Key in WRONG SLOT!!!\n"
                                                    )
                                                    session.query(AMS_Keys).filter(
                                                        AMS_Keys.peg_id
                                                        == ams_can.key_inserted_id
                                                    ).update(
                                                        {
                                                            "current_pos_door_id": 1,
                                                            "current_pos_strip_id": ams_can.key_inserted_position_list,
                                                            "current_pos_slot_no": ams_can.key_inserted_position_slot,
                                                            "keyStatus": SLOT_STATUS_KEY_PRESENT_WRONG_SLOT,
                                                            "keyTakenAtTime": datetime.now(
                                                                TZ_INDIA
                                                            ),
                                                        }
                                                    )
                                                    session.commit()

                                                    ams_can.set_single_LED_state(
                                                        ams_can.key_inserted_position_list,
                                                        ams_can.key_inserted_position_slot,
                                                        CAN_LED_STATE_BLINK,
                                                    )
                                                    keys_msg_print = "Key ret:" + (
                                                        key_record.keyName.ljust(4, " ")
                                                    )
                                                    lcd.clear_display()
                                                    lcd.lcd_string(
                                                        keys_msg_print, lcd.LCD_LINE_2
                                                    )

                                                    eventDesc = get_event_description(
                                                        session,
                                                        EVENT_KEY_RETURNED_WRONG_SLOT,
                                                    )

                                                    ams_event_log = AMS_Event_Log(
                                                        userId=user_auth["id"],
                                                        keyId=key_record.id,
                                                        activityId=act_code_entered,
                                                        eventId=EVENT_KEY_RETURNED_WRONG_SLOT,
                                                        loginType=final_signin_mode,
                                                        access_log_id=ams_access_log.id,
                                                        timeStamp=datetime.now(
                                                            TZ_INDIA
                                                        ),
                                                        event_type=EVENT_TYPE_ALARM,
                                                        eventDesc=eventDesc,
                                                        is_posted=0,
                                                    )
                                                    session.add(ams_event_log)
                                                    session.commit()

                                                    ams_can.key_inserted_event = False
                                                    IS_KEY_IN_WRONG_SLOT = True

                                                    if not ams_can.get_key_id(
                                                        key_record.keyStrip,
                                                        key_record.keyPosition,
                                                    ):
                                                        print(
                                                            "\nKEY INSERTED - Key in WRONG SLOT - LED BLINK for CORRECT SLOT!!!\n"
                                                        )
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
                                                        )
                                                        msg_line2 = (
                                                            "Put in slot "
                                                            + str(correct_key_POS)
                                                            + "  "
                                                        )
                                                        lcd.lcd_string(
                                                            msg_line1, lcd.LCD_LINE_1
                                                        )
                                                        lcd.lcd_string(
                                                            msg_line2, lcd.LCD_LINE_2
                                                        )
                                                        # sleep(0.2)
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
                                                        print(
                                                            "\nKEY INSERTED - Key in WRONG SLOT - Correct Position taken by another KEY!!!\n"
                                                        )
                                                        msg_line1 = "Key in wrong pos"
                                                        lcd.clear_display()
                                                        lcd.lcd_string(
                                                            msg_line1, lcd.LCD_LINE_1
                                                        )
                                                    session.commit()
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
                                                    # IS_KEY_IN_WRONG_SLOT_User_PIN = (
                                                    #     pin_entered
                                                    # )
                                                    BUZZ.write(1)
                                                    sleep(0.5)
                                                    BUZZ.write(0)
                                                    if (
                                                        key_record.keyName
                                                        not in keys_returned_list
                                                    ):
                                                        keys_returned_list.append(
                                                            key_record.keyName
                                                        )

                                            else:
                                                print(
                                                    "\nKEY INSERTED - Key in WRONG SLOT and KEY RECORD not found!!!\n"
                                                )
                                                msg_line1 = "Key record n/a  "
                                                msg_line2 = "Register the key"
                                                lcd.clear_display()

                                                lcd.lcd_string(
                                                    msg_line1, lcd.LCD_LINE_1
                                                )
                                                lcd.lcd_string(
                                                    msg_line2, lcd.LCD_LINE_1
                                                )

                                        timer += 1
                                        if timer % 25 == 0:
                                            lcd.lcd_string(
                                                "You Can Close", lcd.LCD_LINE_1
                                            )
                                            lcd.lcd_string(
                                                "    Door Now   ", lcd.LCD_LINE_2
                                            )
                                        door_status = read_limit_switch(LIMIT_SWITCH)
                                        if door_status == 1:
                                            door_is_open = True
                                        elif door_status == 0:
                                            door_is_open = False

                                    print("############   Step 13  ###########")

                                    DOOR_LOCK.write(0)
                                    BUZZ.write(0)
                                    ams_can.lock_all_positions(1)
                                    ams_can.set_all_LED_OFF(1)
                                    ams_can.lock_all_positions(2)
                                    ams_can.set_all_LED_OFF(2)
                                    lcd.clear_display()

                                    lcd.lcd_string("  Door Closed  ", lcd.LCD_LINE_2)
                                    sleep(0.5)
                                    lcd.clear_display()
                                    ams_access_log.doorCloseTime = datetime.now(
                                        TZ_INDIA
                                    )
                                    ams_access_log.keysAllowed = str(allowed_keys_list)
                                    ams_access_log.keysTaken = str(keys_taken_list)
                                    ams_access_log.keysReturned = str(
                                        keys_returned_list
                                    )
                                    ams_access_log.event_type_id = EVENT_TYPE_EVENT
                                    session.commit()

                                    eventDesc = get_event_description(
                                        session, EVENT_DOOR_CLOSED
                                    )

                                    ams_event_log = AMS_Event_Log(
                                        userId=user_auth["id"],
                                        keyId=None,
                                        activityId=act_code_entered,
                                        eventId=EVENT_DOOR_CLOSED,
                                        loginType=final_signin_mode,
                                        access_log_id=ams_access_log.id,
                                        timeStamp=datetime.now(TZ_INDIA),
                                        event_type=EVENT_TYPE_EVENT,
                                        eventDesc=eventDesc,
                                        is_posted=0,
                                    )
                                    session.add(ams_event_log)
                                    session.commit()
                                    print("############   Step 14  ###########")
                                    if IS_KEY_IN_WRONG_SLOT:
                                        sleep(1)
                                        lcd.lcd_string(
                                            "Key in Wrong Pos", lcd.LCD_LINE_1
                                        )

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
                                        lcd.lcd_string(keys_msg, lcd.LCD_LINE_2)
                                        IS_KEY_IN_WRONG_SLOT = False
                                    continue
                                else:

                                    eventDesc = get_event_description(
                                        session, EVENT_ACTIVITY_CODE_NOT_ALLOWED
                                    )

                                    ams_event_log = AMS_Event_Log(
                                        userId=user_auth["id"],
                                        keyId=None,
                                        activityId=act_code_entered,
                                        eventId=EVENT_ACTIVITY_CODE_NOT_ALLOWED,
                                        loginType=final_signin_mode,
                                        access_log_id=ams_access_log.id,
                                        timeStamp=datetime.now(TZ_INDIA),
                                        event_type=EVENT_TYPE_ALARM,
                                        eventDesc=eventDesc,
                                        is_posted=0,
                                    )
                                    session.add(ams_event_log)
                                    session.commit()
                                    print(
                                        "Activity Code not accepted: Reason - "
                                        + dic_result["Message"]
                                    )
                                    lcd.lcd_string(
                                        (dic_result["Message"]).ljust(16, " "),
                                        lcd.LCD_LINE_2,
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

                elif key_str == "*":

                    is_activity.is_active = 2
                    session.commit()

                    print("############   Step 18  ###########")
                    lcd.clear_display()

                    lcd.lcd_string("Admin PIN:", lcd.LCD_LINE_1)
                    auth_mode, pin_entered = login_using_PIN(
                        session, lcd, key_pad, line=lcd.LCD_LINE_2
                    )
                    lcd.clear_display()

                    lcd.lcd_string("Validating PIN..", lcd.LCD_LINE_2)
                    sleep(1)
                    if not (pin_entered == ""):
                        print("############   Step 19  ###########")
                        user_auth = ams_user.get_user_id(
                            session, AUTH_MODE_PIN, pin_no=pin_entered
                        )
                        print()
                        if user_auth["ResultCode"] == AUTH_RESULT_SUCCESS:
                            print("############   Step 20  ###########")

                            roleId = user_auth["roleId"]
                            if roleId == 1:
                                print("############   Step 21  ###########")
                                lcd.lcd_string("1. Reg. Card    ", lcd.LCD_LINE_1)
                                lcd.lcd_string("2. Reg. Peg", lcd.LCD_LINE_2)

                                key = take_key_pad_input(session, key_pad)

                                if key == "2":
                                    print(ams_can.key_lists)
                                    for keylistid in ams_can.key_lists:
                                        ams_can.unlock_all_positions(keylistid)
                                        ams_can.set_all_LED_ON(keylistid, False)

                                    lcd.clear_display()

                                    keys = (
                                        session.query(AMS_Keys)
                                        .filter(AMS_Keys.keyStatus == 0)
                                        .all()
                                    )
                                    if len(keys) > 0:
                                        lcd.lcd_string("Kindly Insert", lcd.LCD_LINE_1)
                                        lcd.lcd_string("All Pegs", lcd.LCD_LINE_2)
                                        sleep(2)
                                        continue

                                    lcd.lcd_string("Open door...    ", lcd.LCD_LINE_2)

                                    DOOR_LOCK.write(1)
                                    ams_can.door_closed_status = False
                                    sec_counter = 0
                                    door_status = None
                                    
                                    while True:
                                        print(
                                            "############   Waiting for Door to open  ###########"
                                        )
                                        door_status = read_limit_switch(LIMIT_SWITCH)
                                        sleep(1)
                                        sec_counter += 1
                                        if door_status == 0 and sec_counter >= 3:
                                            DOOR_LOCK.write(0)
                                            break
                                        if sec_counter > 5:
                                            DOOR_LOCK.write(0)
                                            break

                                    if door_status == 0:

                                        for keylistid in ams_can.key_lists:
                                            ams_can.lock_all_positions(keylistid)
                                            ams_can.set_all_LED_OFF(keylistid)
                                        lcd.lcd_string(
                                            "WELCOME AMS V1.1", lcd.LCD_LINE_1
                                        )
                                        continue

                                    ams_access_log = AMS_Access_Log(
                                        signInTime=datetime.now(TZ_INDIA),
                                        signInMode=AUTH_MODE_PIN,
                                        signInFailed=0,
                                        signInSucceed=1,
                                        signInUserId=user_auth["id"],
                                        activityCodeEntryTime=None,
                                        activityCode=1,
                                        doorOpenTime=datetime.now(TZ_INDIA),
                                        keysAllowed=None,
                                        keysTaken=None,
                                        keysReturned=None,
                                        doorCloseTime=None,
                                        event_type_id=EVENT_DOOR_OPEN,
                                        is_posted=0,
                                    )
                                    session.add(ams_access_log)
                                    session.commit()

                                    eventDesc = get_event_description(
                                        session, EVENT_DOOR_OPEN
                                    )

                                    ams_event_log = AMS_Event_Log(
                                        userId=user_auth["id"],
                                        keyId=None,
                                        activityId=1,
                                        eventId=EVENT_DOOR_OPEN,
                                        loginType="PIN",
                                        access_log_id=ams_access_log.id,
                                        timeStamp=datetime.now(TZ_INDIA),
                                        event_type=EVENT_TYPE_EVENT,
                                        eventDesc=eventDesc,
                                        is_posted=0,
                                    )
                                    session.add(ams_event_log)
                                    session.commit()

                                    eventDesc = get_event_description(
                                        session, EVENT_PEG_REGISTERATION
                                    )

                                    ams_event_log = AMS_Event_Log(
                                        userId=user_auth["id"],
                                        keyId=None,
                                        activityId=1,
                                        eventId=EVENT_PEG_REGISTERATION,
                                        loginType="PIN",
                                        access_log_id=ams_access_log.id,
                                        timeStamp=datetime.now(TZ_INDIA),
                                        event_type=EVENT_PEG_REGISTERATION,
                                        eventDesc=eventDesc,
                                        is_posted=0,
                                    )
                                    session.add(ams_event_log)
                                    session.commit()

                                    lcd.lcd_string("Keys Available", lcd.LCD_LINE_1)
                                    lcd.lcd_string("Press ENTER", lcd.LCD_LINE_2)

                                    key = take_key_pad_input(session, key_pad)
                                    print(key)

                                    if key == "#":

                                        DOOR_LOCK.write(0)

                                        ams_can.door_closed_status = True

                                        lcd.lcd_string(
                                            "Scan in progress", lcd.LCD_LINE_1
                                        )
                                        lcd.lcd_string(
                                            "Pls Wait...     ", lcd.LCD_LINE_2
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
                                                print(f"peg_id is {peg_id}")
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
                                                        )
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
                                                            .first()
                                                        )
                                                        print(key)
                                                        key.peg_id = peg_id
                                                        key.current_pos_strip_id = (
                                                            keylistid
                                                        )
                                                        key.current_pos_slot_no = slot
                                                        session.commit()
                                                        lcd.lcd_string(
                                                            peg_display_msg,
                                                            lcd.LCD_LINE_2,
                                                        )
                                                        sleep(0.5)
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
                                                            .first()
                                                        )
                                                        print(key)
                                                        key.peg_id = peg_id
                                                        key.current_pos_strip_id = (
                                                            keylistid
                                                        )
                                                        key.current_pos_slot_no = slot
                                                        session.commit()

                                                        peg_display_msg = (
                                                            "Key "
                                                            + str(key_pos_no)
                                                            + " reg. done"
                                                        )
                                                        lcd.lcd_string(
                                                            peg_display_msg,
                                                            lcd.LCD_LINE_2,
                                                        )
                                                        sleep(0.5)
                                                ams_can.set_single_LED_state(
                                                    keylistid, slot, CAN_LED_STATE_OFF
                                                )

                                    eventDesc = get_event_description(
                                        session, EVENT_DOOR_CLOSED
                                    )

                                    ams_event_log = AMS_Event_Log(
                                        userId=user_auth["id"],
                                        keyId=None,
                                        activityId=1,
                                        eventId=EVENT_DOOR_CLOSED,
                                        loginType="PIN",
                                        access_log_id=ams_access_log.id,
                                        timeStamp=datetime.now(TZ_INDIA),
                                        event_type=EVENT_TYPE_EVENT,
                                        eventDesc=eventDesc,
                                        is_posted=0,
                                    )
                                    session.add(ams_event_log)
                                    session.commit()

                                    for kgetCardDetailseylistid in ams_can.key_lists:
                                        ams_can.lock_all_positions(keylistid)
                                        ams_can.set_all_LED_OFF(keylistid)

                                    ams_can.door_closed_status = True
                                    lcd.lcd_string("WELCOME AMS V1.1", 1)
                                    continue

                                elif key == "1":
                                    print("############   Step 22  ###########")
                                    lcd.clear_display()

                                    lcd.lcd_string("User PIN:", lcd.LCD_LINE_1)
                                    auth_mode, pin_entered = login_using_PIN(
                                        session, lcd, key_pad, line=lcd.LCD_LINE_1
                                    )
                                    lcd.lcd_string("Validating PIN..", lcd.LCD_LINE_2)
                                    print(f"entered pin is: {pin_entered}")
                                    if not (pin_entered == ""):
                                        user_auth = ams_user.get_user_id(
                                            session, AUTH_MODE_PIN, pin_no=pin_entered
                                        )
                                        if (
                                            user_auth["ResultCode"]
                                            == AUTH_RESULT_SUCCESS
                                        ):
                                            lcd.clear_display()

                                            lcd.lcd_string(
                                                "Swipe User Card ", lcd.LCD_LINE_1
                                            )
                                            timer_sec = 0
                                            card_no = None
                                            card_no_updated = False
                                            card_already_assigned = False
                                            recordset = None
                                            while (
                                                timer_sec < 30
                                                and not card_already_assigned
                                            ):
                                                timer_sec += 1
                                                card_no = int(
                                                    card_reader.get_card_no(
                                                        card_reader.ser
                                                    )
                                                )
                                                sleep(1)
                                                print(f"card number is: {card_no}")
                                                if card_no == 0:
                                                    break
                                                recordset = (
                                                    session.query(AMS_Users)
                                                    .filter(
                                                        AMS_Users.cardNo
                                                        == str(card_no),
                                                        AMS_Users.id != user_auth["id"],
                                                        AMS_Users.deletedAt == None,
                                                    )
                                                    .first()
                                                )
                                                print(recordset)
                                                if recordset:
                                                    card_already_assigned = True
                                                if card_no and recordset is None:
                                                    session.query(AMS_Users).filter(
                                                        AMS_Users.id == user_auth["id"]
                                                    ).update({"cardNo": str(card_no)})
                                                    card_no_updated = True
                                                    session.commit()
                                                    break

                                            if card_no_updated:
                                                lcd.clear_display()

                                                lcd.lcd_string(
                                                    "Card Registered", lcd.LCD_LINE_1
                                                )
                                                msg = "for " + user_auth["name"]
                                                lcd.lcd_string(msg, lcd.LCD_LINE_2)

                                                eventDesc = get_event_description(
                                                    session,
                                                    EVENT_CARD_REGISTRATION_SUCCESS,
                                                )

                                                ams_event_log = AMS_Event_Log(
                                                    userId=user_auth["id"],
                                                    keyId=None,
                                                    activityId=None,
                                                    eventId=EVENT_CARD_REGISTRATION_SUCCESS,
                                                    loginType="PIN",
                                                    access_log_id=None,
                                                    timeStamp=datetime.now(TZ_INDIA),
                                                    event_type=EVENT_TYPE_EVENT,
                                                    eventDesc=eventDesc,
                                                    is_posted=0,
                                                )
                                                session.add(ams_event_log)
                                                session.commit()

                                                sleep(2)
                                            elif card_already_assigned:
                                                lcd.clear_display()

                                                lcd.lcd_string(
                                                    "Card Already", lcd.LCD_LINE_1
                                                )
                                                lcd.lcd_string(
                                                    "Assigned !", lcd.LCD_LINE_2
                                                )

                                                eventDesc = get_event_description(
                                                    session,
                                                    EVENT_CARD_REGISTRATION_FAILURE,
                                                )

                                                ams_event_log = AMS_Event_Log(
                                                    userId=user_auth["id"],
                                                    keyId=None,
                                                    activityId=None,
                                                    eventId=EVENT_CARD_REGISTRATION_FAILURE,
                                                    loginType="PIN",
                                                    access_log_id=None,
                                                    timeStamp=datetime.now(TZ_INDIA),
                                                    event_type=EVENT_TYPE_ALARM,
                                                    eventDesc=eventDesc,
                                                    is_posted=0,
                                                )
                                                session.add(ams_event_log)
                                                session.commit()

                                                sleep(2)
                                            else:
                                                lcd.clear_display()

                                                lcd.lcd_string(
                                                    "Card not reg.", lcd.LCD_LINE_1
                                                )
                                                lcd.lcd_string(
                                                    "Try again later.", lcd.LCD_LINE_2
                                                )
                                                eventDesc = get_event_description(
                                                    session,
                                                    EVENT_CARD_REGISTRATION_FAILURE,
                                                )

                                                ams_event_log = AMS_Event_Log(
                                                    userId=user_auth["id"],
                                                    keyId=None,
                                                    activityId=None,
                                                    eventId=EVENT_CARD_REGISTRATION_FAILURE,
                                                    loginType="PIN",
                                                    access_log_id=None,
                                                    timeStamp=datetime.now(TZ_INDIA),
                                                    event_type=EVENT_TYPE_ALARM,
                                                    eventDesc=eventDesc,
                                                    is_posted=0,
                                                )
                                                session.add(ams_event_log)
                                                session.commit()
                                                sleep(2)
                                            continue

                                else:
                                    lcd.clear_display()

                                    lcd.lcd_string("Wrong Input", lcd.LCD_LINE_1)
                                    sleep(2)
                                    continue

                            else:
                                lcd.lcd_string("                ", 2)
                                lcd.lcd_string("User not admin!", 2)
                                sleep(2)
                                continue

                elif key_str == "0":
                    is_activity.is_active = 2
                    session.commit()

                    print("############   Step 19  ###########")
                    lcd.clear_display()

                    lcd.lcd_string("Admin PIN:", lcd.LCD_LINE_1)
                    auth_mode, pin_entered = login_using_PIN(
                        session, lcd, key_pad, line=lcd.LCD_LINE_2
                    )
                    lcd.clear_display()

                    lcd.lcd_string("Validating PIN..", lcd.LCD_LINE_2)
                    sleep(1)
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
                                lcd.lcd_string("Take/Return Keys", lcd.LCD_LINE_2)
                                ams_can.unlock_all_positions(1)
                                ams_can.set_all_LED_ON(1, False)

                                ams_can.unlock_all_positions(2)
                                ams_can.set_all_LED_ON(2, False)
                                DOOR_LOCK.write(1)
                                ams_can.door_closed_status = False

                                print(f"user id is : {user_auth['id']}")

                                ams_access_log = AMS_Access_Log(
                                    signInTime=datetime.now(TZ_INDIA),
                                    signInMode=AUTH_MODE_PIN,
                                    signInFailed=0,
                                    signInSucceed=1,
                                    signInUserId=user_auth["id"],
                                    activityCodeEntryTime=None,
                                    activityCode=1,
                                    doorOpenTime=datetime.now(TZ_INDIA),
                                    keysAllowed=None,
                                    keysTaken=None,
                                    keysReturned=None,
                                    doorCloseTime=None,
                                    event_type_id=EVENT_DOOR_OPEN,
                                    is_posted=0,
                                )
                                session.add(ams_access_log)
                                session.commit()

                                eventDesc = get_event_description(
                                    session, EVENT_DOOR_OPEN
                                )

                                ams_event_log = AMS_Event_Log(
                                    userId=user_auth["id"],
                                    keyId=None,
                                    activityId=1,
                                    eventId=EVENT_DOOR_OPEN,
                                    loginType="PIN",
                                    access_log_id=ams_access_log.id,
                                    timeStamp=datetime.now(TZ_INDIA),
                                    event_type=EVENT_TYPE_EVENT,
                                    eventDesc=eventDesc,
                                    is_posted=0,
                                )
                                session.add(ams_event_log)
                                session.commit()

                                keys_taken_list = []
                                keys_returned_list = []
                                door_is_open = True
                                sec_counter = 0
                                while door_is_open:
                                    door_status = read_limit_switch(LIMIT_SWITCH)
                                    print(f"door status is: {door_status}")
                                    sleep(0.2)
                                    sec_counter += 1
                                    if door_status == 1:
                                        door_is_open = True
                                    elif door_status == 0 and sec_counter >= 25:
                                        door_is_open = False
                                        DOOR_LOCK.write(0)
                                        break

                                    if sec_counter == 25:
                                        print(
                                            "inside threshold reached status!!!!!!!!!!!!"
                                        )
                                        DOOR_LOCK.write(0)
                                        ams_can.door_closed_status = True

                                    (
                                        keys_taken_list,
                                        keys_returned_list,
                                    ) = get_key_interactions(
                                        ams_can,
                                        session,
                                        cabinet,
                                        ams_access_log,
                                        user_auth,
                                        lcd,
                                        keys_taken_list,
                                        keys_returned_list,
                                    )

                                    if sec_counter >= 300:
                                        lcd.clear_display()

                                        lcd.lcd_string(
                                            "Door opened too ", lcd.LCD_LINE_1
                                        )
                                        lcd.lcd_string(
                                            "long, close door", lcd.LCD_LINE_2
                                        )
                                        BUZZ.write(1)
                                        sleep(2)
                                        while True:
                                            door_status = read_limit_switch(
                                                LIMIT_SWITCH
                                            )
                                            if door_status == 0:
                                                break
                                        break
                                DOOR_LOCK.write(0)
                                BUZZ.write(0)
                                ams_can.lock_all_positions(1)
                                ams_can.set_all_LED_OFF(1)
                                ams_can.lock_all_positions(2)
                                ams_can.set_all_LED_OFF(2)
                                lcd.clear_display()

                                global counter
                                counter = 0
                                lcd.lcd_string("  Door Closed  ", lcd.LCD_LINE_2)

                                ams_access_log.keysAllowed = ""
                                print(keys_taken_list, keys_returned_list)
                                ams_access_log.keysTaken = str(keys_taken_list)
                                ams_access_log.keysReturned = str(keys_returned_list)
                                ams_access_log.event_type_id = EVENT_TYPE_EVENT
                                ams_access_log.doorCloseTime = datetime.now(TZ_INDIA)
                                session.commit()

                                eventDesc = get_event_description(
                                    session, EVENT_DOOR_CLOSED
                                )

                                ams_event_log = AMS_Event_Log(
                                    userId=user_auth["id"],
                                    keyId=None,
                                    activityId=1,
                                    eventId=EVENT_DOOR_CLOSED,
                                    loginType="PIN",
                                    access_log_id=ams_access_log.id,
                                    timeStamp=datetime.now(TZ_INDIA),
                                    event_type=EVENT_TYPE_EVENT,
                                    eventDesc=eventDesc,
                                    is_posted=0,
                                )
                                session.add(ams_event_log)
                                session.commit()

                                continue

            except Exception as e:
                session.close()
                ams_can.cleanup()
                BUZZ.write(0)
                DOOR_LOCK.write(0)
                print("Exited AMS-CORE app due to interrupt")
                print(e)
                break
    else:
        lcd.lcd_string("AMS not active! ", 2)
        session.close()
        return


if __name__ == "__main__":
    while True:
        try:
            main()
            sleep(2)
        except Exception as e:
            print(e)
