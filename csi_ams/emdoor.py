import schedule
from model import *
from amscan import *
from utils import lcd
from time import sleep
from threading import Lock
from utils.commons import *
from datetime import datetime
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker


LAST_ACK_TIME = datetime.now(TZ_INDIA)
ACK_COUNTER = 0
LAST_ACK_TIME_WK = datetime.now(TZ_INDIA)
ACK_COUNTER_WK = 0
THRESHOLD = 5


def get_wrong_key_placed_too_long_status(
    ams_can,
    session,
    lcd,
    cabinet,
):

    global TZ_INDIA
    global ACK_COUNTER_WK
    global LAST_ACK_TIME_WK

    print(
        "############### inside wrong key placed for too long status ###################"
    )

    is_activity = (
        session.query(AMS_Activity_Progress_Status)
        .filter(AMS_Activity_Progress_Status.id == 1)
        .one_or_none()
    )
    if is_activity.is_active == 2 or is_activity.is_active == CABINET_SHUTDOWN_INT:
        return

    mutex.acquire()
    keys_taken = (
        session.query(AMS_Keys)
        .filter(
            AMS_Keys.keyStatus == 2,
            AMS_Keys.keyTakenAtTime != None,
            AMS_Keys.keyTimeout != None,
            AMS_Keys.keyTimeout != "",
        )
        .all()
    )

    keys_taken_list_with_time = []
    is_limit_reached = []
    current_time = datetime.now(TZ_INDIA)
    print(f"current time is: {current_time}")

    if keys_taken != []:
        keys_taken_list_with_time = [
            (key.keyName, key.keyTakenAtTime.astimezone(TZ_INDIA), int(key.keyTimeout))
            for key in keys_taken
        ]

        print(keys_taken_list_with_time)

        for key in keys_taken:
            try:
                key_taken_time = key.keyTakenAtTime.astimezone(TZ_INDIA)
                key_taken_timeout = int(key.keyTimeout)
                print(
                    f"################################# key taken time: {key_taken_time} #############################"
                )
                print(
                    f"################################# key taken timeout: {key_taken_timeout} #############################"
                )
                print(
                    f"Number of minutes: {(current_time - key_taken_time).total_seconds() // 60}"
                )

                if (
                    (current_time - key_taken_time).total_seconds() // 60
                ) >= key_taken_timeout:
                    is_limit_reached.append(key)

            except Exception as e:
                print("exception occured in key data collection.")
                continue
    else:
        ACK_COUNTER_WK = 0
        mutex.release()
        return

    key_took_at = None
    if len(is_limit_reached) > 0:
        limit_reached_keys = [
            (key.keyName, key.keyTakenAtTime) for key in is_limit_reached
        ]
        print(
            f"following wrong placed keys have reached their limits: {limit_reached_keys}"
        )
        key_took_at = min([key.keyAck.astimezone(TZ_INDIA) for key in is_limit_reached])
        LAST_ACK_TIME_WK = key_took_at
    else:
        print("no key has reached limit!")

    print(f"last acknowledgement: {LAST_ACK_TIME_WK}")
    time_diff = current_time - LAST_ACK_TIME_WK

    if time_diff.total_seconds() // 60 >= THRESHOLD and key_took_at != None:
        if len(keys_taken_list_with_time) > 0:

            is_activity.is_active = 1
            session.commit()

            lcd.clear_display()
            BUZZ.write(1)
            current_time = datetime.now(TZ_INDIA)
            out_keys = []
            out_keys_ids = []
            for key in is_limit_reached:
                if (
                    (current_time - key.keyAck.astimezone(TZ_INDIA)).total_seconds()
                    // 60
                ) >= THRESHOLD:
                    out_keys.append(key.keyName[4:])
                    out_keys_ids.append(key.id)
            out_keys.sort()
            out_keys_str = ",".join(out_keys)
            print(out_keys_str)
            lcd.lcd_string(
                f"WRONG: {out_keys_str}",
                lcd.LCD_LINE_1,
            )

            sleep(2)
            lcd.lcd_string("Press 1 For ACK.", lcd.LCD_LINE_2)

            print(
                "##############################################\nBuzzer is on\n################################################"
            )

            eventDesc = get_event_description(
                session, EVENT_ALARM_GENERATION_WRONG_KEY_PLACED_TOO_LONG
            )
            for idx in out_keys_ids:
                ams_event_log = AMS_Event_Log(
                    userId=None,
                    keyId=idx,
                    activityId=None,
                    eventId=EVENT_ALARM_GENERATION_WRONG_KEY_PLACED_TOO_LONG,
                    loginType=None,
                    access_log_id=None,
                    timeStamp=datetime.now(TZ_INDIA),
                    event_type=EVENT_TYPE_ALARM,
                    eventDesc=eventDesc,
                    is_posted=0,
                )
                session.add(ams_event_log)
                session.commit()

            key = ""
            while True:
                key = take_key_pad_input(session, key_pad)
                if key == "1":
                    break

            is_activity.is_active = 0
            session.commit()
            eventDesc = get_event_description(
                session, EVENT_WRONG_KEY_PLACED_TOO_LONG_ACK
            )

            for idx in out_keys_ids:
                ams_event_log = AMS_Event_Log(
                    userId=None,
                    keyId=idx,
                    activityId=None,
                    eventId=EVENT_WRONG_KEY_PLACED_TOO_LONG_ACK,
                    loginType=None,
                    access_log_id=None,
                    timeStamp=datetime.now(TZ_INDIA),
                    event_type=EVENT_TYPE_ALARM,
                    eventDesc=eventDesc,
                    is_posted=0,
                )
                session.add(ams_event_log)
                session.commit()

            BUZZ.write(0)
            current_time = datetime.now(TZ_INDIA)
            LAST_ACK_TIME_WK = datetime.now(TZ_INDIA)
            for key in is_limit_reached:
                if (
                    (current_time - key.keyAck.astimezone(TZ_INDIA)).total_seconds()
                    // 60
                ) >= THRESHOLD:
                    key.keyAck = LAST_ACK_TIME_WK
            session.commit()
            ACK_COUNTER_WK += 1

            sleep(1)
            lcd.clear_display()
            show_ideal_msg(lcd, cabinet)

    is_activity.is_active = 0
    session.commit()
    mutex.release()
    return


def get_key_taken_too_long_status(
    ams_can,
    session,
    lcd,
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
    if is_activity.is_active == 2 or is_activity.is_active == CABINET_SHUTDOWN_INT:
        return

    mutex.acquire()
    keys_taken = (
        session.query(AMS_Keys)
        .filter(
            AMS_Keys.keyStatus == 0,
            AMS_Keys.keyTakenAtTime != None,
            AMS_Keys.keyTimeout != None,
            AMS_Keys.keyTimeout != "",
        )
        .all()
    )

    keys_taken_list_with_time = []
    is_limit_reached = []
    current_time = datetime.now(TZ_INDIA)
    print(f"current time is: {current_time}")

    if keys_taken != []:
        keys_taken_list_with_time = [
            (key.keyName, key.keyTakenAtTime.astimezone(TZ_INDIA), int(key.keyTimeout))
            for key in keys_taken
        ]

        print(keys_taken_list_with_time)

        for key in keys_taken:
            try:
                key_taken_time = key.keyTakenAtTime.astimezone(TZ_INDIA)
                key_taken_timeout = int(key.keyTimeout)
                print(
                    f"################################# key taken time: {key_taken_time} #############################"
                )
                print(
                    f"################################# key taken timeout: {key_taken_timeout} #############################"
                )
                print(
                    f"Number of minutes: {(current_time - key_taken_time).total_seconds() // 60}"
                )

                if (
                    (current_time - key_taken_time).total_seconds() // 60
                ) >= key_taken_timeout:
                    is_limit_reached.append(key)

            except Exception as e:
                print("exception occured in key data collection.")
                continue
    else:
        ACK_COUNTER = 0
        mutex.release()
        return

    key_took_at = None
    if len(is_limit_reached) > 0:
        limit_reached_keys = [
            (key.keyName, key.keyTakenAtTime) for key in is_limit_reached
        ]
        print(f"following keys have reached their limits: {limit_reached_keys}")
        key_took_at = min([key.keyAck.astimezone(TZ_INDIA) for key in is_limit_reached])
        LAST_ACK_TIME = key_took_at
    else:
        print("no key has reached limit!")

    print(f"last acknowledgement: {LAST_ACK_TIME}")
    time_diff = current_time - LAST_ACK_TIME

    if time_diff.total_seconds() // 60 >= THRESHOLD and key_took_at != None:
        if len(keys_taken_list_with_time) > 0:

            is_activity.is_active = 1
            session.commit()

            lcd.clear_display()
            BUZZ.write(1)
            current_time = datetime.now(TZ_INDIA)
            out_keys = []
            out_keys_ids = []
            for key in is_limit_reached:
                if (
                    (current_time - key.keyAck.astimezone(TZ_INDIA)).total_seconds()
                    // 60
                ) >= THRESHOLD:
                    out_keys.append(key.keyName[4:])
                    out_keys_ids.append(key.id)
            out_keys.sort()
            out_keys_str = ",".join(out_keys)
            print(out_keys_str)
            lcd.lcd_string(
                f"OUT: {out_keys_str}",
                lcd.LCD_LINE_1,
            )

            sleep(2)
            lcd.lcd_string("Press 1 For ACK.", lcd.LCD_LINE_2)

            print(
                "##############################################\nBuzzer is on\n################################################"
            )

            eventDesc = get_event_description(
                session, EVENT_ALARM_GENERATION_KEY_TAKEN_TOO_LONG
            )
            for idx in out_keys_ids:
                ams_event_log = AMS_Event_Log(
                    userId=None,
                    keyId=idx,
                    activityId=None,
                    eventId=EVENT_ALARM_GENERATION_KEY_TAKEN_TOO_LONG,
                    loginType=None,
                    access_log_id=None,
                    timeStamp=datetime.now(TZ_INDIA),
                    event_type=EVENT_TYPE_ALARM,
                    eventDesc=eventDesc,
                    is_posted=0,
                )
                session.add(ams_event_log)
                session.commit()

            key = ""
            while True:
                key = take_key_pad_input(session, key_pad)
                if key == "1":
                    break

            eventDesc = get_event_description(session, EVENT_KEY_TAKEN_TOO_LONG_ACK)

            for idx in out_keys_ids:
                ams_event_log = AMS_Event_Log(
                    userId=None,
                    keyId=idx,
                    activityId=None,
                    eventId=EVENT_KEY_TAKEN_TOO_LONG_ACK,
                    loginType=None,
                    access_log_id=None,
                    timeStamp=datetime.now(TZ_INDIA),
                    event_type=EVENT_TYPE_ALARM,
                    eventDesc=eventDesc,
                    is_posted=0,
                )
                session.add(ams_event_log)
                session.commit()

            BUZZ.write(0)
            current_time = datetime.now(TZ_INDIA)
            LAST_ACK_TIME = datetime.now(TZ_INDIA)
            for key in is_limit_reached:
                if (
                    (current_time - key.keyAck.astimezone(TZ_INDIA)).total_seconds()
                    // 60
                ) >= THRESHOLD:
                    key.keyAck = LAST_ACK_TIME
            session.commit()
            ACK_COUNTER += 1

            sleep(1)
            lcd.clear_display()
            show_ideal_msg(lcd, cabinet)

    is_activity.is_active = 0
    session.commit()
    mutex.release()
    return


if __name__ == "__main__":

    try:
        sleep(25)
        ams_can = AMS_CAN()
        sleep(5)
    except Exception as e:
        print(e)

    engine = create_engine(
        SQLALCHEMY_DATABASE_URI, connect_args={"check_same_thread": False}
    )
    Session = sessionmaker()
    Session.configure(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    mutex = Lock()
    cabinet = session.query(AMS_Cabinet).one_or_none()

    keys_taken = (
        session.query(AMS_Keys)
        .filter(
            AMS_Keys.keyStatus != 1,
            AMS_Keys.keyTakenAtTime != None,
        )
        .all()
    )
    for key in keys_taken:
        key.keyAck = key.keyTakenAtTime

    session.commit()

    schedule.every(30).seconds.do(
        get_key_taken_too_long_status, ams_can, session, lcd, cabinet
    )

    schedule.every(20).seconds.do(
        get_wrong_key_placed_too_long_status, ams_can, session, lcd, cabinet
    )

    while True:
        try:
            schedule.run_pending()
            sleep(1)
        except Exception as e:
            print(e)
