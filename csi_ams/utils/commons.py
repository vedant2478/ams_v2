import sys
import mraa
import threading
from . import bms
from csi_ams.model import *
from csi_ams.amscan import *
import _thread as thread
from datetime import datetime
from csi_ams.utils import lcd, keypad, card_reader


AUTH_MODE_PIN = 1
AUTH_MODE_CARD = 2

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
EVENT_PEG_REGISTERATION = 15
EVENT_KEY_TAKEN_TOO_LONG_ACK = 16
EVENT_WRONG_KEY_PLACED_TOO_LONG_ACK = 17
EVENT_CARD_REGISTRATION_SUCCESS = 18
EVENT_CARD_REGISTRATION_FAILURE = 19
EVENT_ALARM_GENERATION_KEY_TAKEN_TOO_LONG = 20
EVENT_ALARM_GENERATION_WRONG_KEY_PLACED_TOO_LONG = 21


EVENT_TYPE_EVENT = 1
EVENT_TYPE_ALARM = 2

SLOT_STATUS_KEY_NOT_PRESENT = 0
SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT = 1
SLOT_STATUS_KEY_PRESENT_WRONG_SLOT = 2

MAIN_DOOR_LOCK = 0
MAIN_DOOR_UN_LOCK = 1

BUZZER_PIN = 37
DOOR_LOCK_PIN = 40
LIMIT_SWITCH_PIN = 32
BUZZ = mraa.Gpio(BUZZER_PIN)
DOOR_LOCK = mraa.Gpio(DOOR_LOCK_PIN)
LIMIT_SWITCH = mraa.Gpio(LIMIT_SWITCH_PIN)
DOOR_LOCK.dir(mraa.DIR_OUT)
BUZZ.dir(mraa.DIR_OUT)
LIMIT_SWITCH.dir(mraa.DIR_IN)

TZ_INDIA = pytz.timezone("Asia/Kolkata")
CABINET_SHUTDOWN_INT = 7
key_pad = keypad.MyKeyboard()
counter = 0


SQLALCHEMY_DATABASE_URI = (
    "sqlite:////home/rock/Desktop/csi_ams/csiams.dev.sqlite"
)


def quit_function(fn_name):
    print(f"inside function {fn_name}")
    print("\n\tTIMEOUT!!! Press any key", file=sys.stderr)
    thread.interrupt_main()


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
def login_using_PIN(session, lcd, key_pad, line=lcd.LCD_LINE_2):
    pin_char_count = 0
    pin_entered = ""
    while pin_char_count < 5:
        key = take_key_pad_input(session, key_pad)
        if key is not None:
            if key.isnumeric():
                pin_entered = pin_entered + key
                lcd.lcd_string("*" * len(pin_entered), line)
                pin_char_count = pin_char_count + 1
                print(f"pin entered so far: {pin_entered}")
            elif key == "#":
                return AUTH_MODE_PIN, pin_entered
    return AUTH_MODE_PIN, pin_entered


@exit_after(60)
def login_using_PIN_Card(lcd, key_pad, session):

    lcd.clear_display()

    Card_No = 0
    login_option = ""
    login_option_str = ""

    lcd.lcd_string("Login Option", lcd.LCD_LINE_1)
    lcd.lcd_string("1. Card   2. Pin", lcd.LCD_LINE_2)

    login_option = take_key_pad_input(session, key_pad)
    if login_option == "1":
        lcd.clear_display()

        lcd.lcd_string("Swipe your card ...", lcd.LCD_LINE_1)
        time_sec = 0
        while True:
            Card_No = int(card_reader.get_card_no(card_reader.ser))
            print(f"card number is: {Card_No}")
            if Card_No == 0:
                break
            if Card_No > 0 or time_sec >= 15:
                break
            time_sec += 1

        if Card_No > 0:
            return AUTH_MODE_CARD, Card_No
        else:
            lcd.lcd_string(" TIMEOUT!!! ", lcd.LCD_LINE_1)
            sleep(2)
            return AUTH_MODE_CARD, Card_No

    elif login_option == "2":
        lcd.clear_display()

        lcd.lcd_string("Enter PIN:", lcd.LCD_LINE_1)
        return login_using_PIN(session, lcd, key_pad)

    else:
        lcd.clear_display()

        lcd.lcd_string("Wrong Input", lcd.LCD_LINE_1)
        sleep(2)
        return -1, 0


@exit_after(60)
def get_activity_code(session, lcd, key_pad):
    act_char_count = 0
    act_code_entered = ""
    while act_char_count < 2:
        key = take_key_pad_input(session, key_pad)
        if key is not None and key.isnumeric():
            act_code_entered = act_code_entered + key
            lcd.lcd_string(act_code_entered, lcd.LCD_LINE_2)
            act_char_count = act_char_count + 1
        elif key == "#":
            return act_code_entered
    return act_code_entered


def play_emergency_music(BUZZ):
    i = 0
    while i < 4:
        BUZZ.write(1)
        sleep(0.5)
        BUZZ.write(0)
        sleep(0.5)
        i += 1


def show_ideal_msg(lcd, cabinet):
    BATTERY_CHARGE_PC = str(bms.get_batt_pct(bms.ser))
    lcd.lcd_string(f"HPCL KMS    {BATTERY_CHARGE_PC}%", lcd.LCD_LINE_1)
    lcd.lcd_string(f"RO CODE:{cabinet.site.siteName}", lcd.LCD_LINE_2)


def read_limit_switch(LIMIT_SWITCH):
    value = LIMIT_SWITCH.read()
    return int(value)


def take_key_pad_input(session, key_pad):
    key_str = None
    while key_str is None:
        key_str = key_pad.ReadKey()
    return key_str


def update_keys_status(ams_can, list_ID, session):
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
                    and current_key.is_critical == 1
                ):
                    current_key.color = "Red"
                    current_key.keyStatus = SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT
                if (
                    current_key.current_pos_slot_no == current_key.keyPosition
                    and current_key.current_pos_strip_id == current_key.keyStrip
                    and current_key.is_critical == 0
                ):
                    current_key.color = "Green"
                    current_key.keyStatus = SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT
                if (
                    current_key.current_pos_slot_no != current_key.keyPosition
                    or current_key.current_pos_strip_id != current_key.keyStrip
                ):
                    current_key.color = "Black"
                    current_key.keyStatus = SLOT_STATUS_KEY_PRESENT_WRONG_SLOT
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


def get_event_description(session, event_status):
    event_type = (
        session.query(AMS_Event_Types)
        .filter(AMS_Event_Types.eventId == event_status)
        .one_or_none()
    )
    return event_type.eventDescription


def get_key_interactions(
    ams_can2,
    session,
    cabinet,
    ams_access_log,
    user_auth,
    lcd,
    keys_taken_list,
    keys_returned_list,
):
    global counter
    key_record = None

    if ams_can2.key_taken_event:
        counter = 0
        print("############   Key has been taken out  ###########")
        for key in cabinet.keys:
            if key.peg_id == ams_can2.key_taken_id:
                key_record = key
                break

        if key_record:
            keys_msg_print = "Key taken:" + (key_record.keyName.ljust(4, " "))
            print(keys_msg_print)

            session.query(AMS_Keys).filter(
                AMS_Keys.peg_id == ams_can2.key_taken_id
            ).update(
                {
                    "keyTakenBy": user_auth["id"],
                    "keyTakenByUser": user_auth["name"],
                    "current_pos_strip_id": None,
                    "current_pos_slot_no": None,
                    "keyTakenAtTime": datetime.now(TZ_INDIA),
                    "keyStatus": SLOT_STATUS_KEY_NOT_PRESENT,
                    "color": "White",
                }
            )
            session.commit()

            eventDesc = get_event_description(session, EVENT_KEY_TAKEN_CORRECT)

            ams_event_log = AMS_Event_Log(
                userId=user_auth["id"],
                keyId=key_record.id,
                activityId=None,
                eventId=EVENT_KEY_TAKEN_CORRECT,
                loginType="PIN",
                access_log_id=ams_access_log.id,
                timeStamp=datetime.now(TZ_INDIA),
                event_type=EVENT_TYPE_EVENT,
                eventDesc=eventDesc,
                is_posted=0,
            )
            session.add(ams_event_log)
            session.commit()

            if key_record.keyName not in keys_taken_list:
                keys_taken_list.append(key_record.keyName)
        else:
            print("Key taken but key record not found for updating taken event")
            keys_msg_print = "Key not reg.    "

        lcd.clear_display()
        lcd.lcd_string(keys_msg_print, lcd.LCD_LINE_2)

        ams_can2.key_taken_event = False

    elif ams_can2.key_inserted_event:
        counter = 0
        print("############   key has been inserted  ###########")

        for key in cabinet.keys:
            if key.peg_id == ams_can2.key_inserted_id:
                key_record = key
                break

        if key_record:
            if (
                key_record.keyStrip == ams_can2.key_inserted_position_list
                and key_record.keyPosition == ams_can2.key_inserted_position_slot
            ):
                print("\n\nKEY INSERTED - Key in Correct Slot identified\n\n")
                ams_can2.set_single_LED_state(
                    ams_can2.key_inserted_position_list,
                    ams_can2.key_inserted_position_slot,
                    CAN_LED_STATE_OFF,
                )

                keys_msg_print = "Key ret:" + (key_record.keyName.ljust(4, " "))
                lcd.clear_display()
                lcd.lcd_string(keys_msg_print, lcd.LCD_LINE_2)

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
                print("\n\nKEY INSERTED - Keys table updated\n\n")

                eventDesc = get_event_description(
                    session, EVENT_KEY_RETURNED_RIGHT_SLOT
                )

                ams_event_log = AMS_Event_Log(
                    userId=user_auth["id"],
                    keyId=key_record.id,
                    activityId=None,
                    eventId=EVENT_KEY_RETURNED_RIGHT_SLOT,
                    loginType="PIN",
                    access_log_id=ams_access_log.id,
                    timeStamp=datetime.now(TZ_INDIA),
                    event_type=EVENT_TYPE_EVENT,
                    eventDesc=eventDesc,
                    is_posted=0,
                )
                session.add(ams_event_log)
                session.commit()

                ams_can2.key_inserted_event = False
                if key_record.keyName not in keys_returned_list:
                    keys_returned_list.append(key_record.keyName)

            elif (
                key_record.keyStrip != ams_can2.key_inserted_position_list
                or key_record.keyPosition != ams_can2.key_inserted_position_slot
            ):
                print("\n\nKEY INSERTED - In WRONG slot identified\n\n")
                ams_can2.set_single_LED_state(
                    ams_can2.key_inserted_position_list,
                    ams_can2.key_inserted_position_slot,
                    CAN_LED_STATE_BLINK,
                )

                keys_msg_print = "Key ret:" + (key_record.keyName.ljust(4, " "))
                lcd.clear_display()
                lcd.lcd_string(keys_msg_print, lcd.LCD_LINE_2)

                session.query(AMS_Keys).filter(
                    AMS_Keys.peg_id == ams_can2.key_inserted_id
                ).update(
                    {
                        "current_pos_door_id": 1,
                        "current_pos_strip_id": ams_can2.key_inserted_position_list,
                        "current_pos_slot_no": ams_can2.key_inserted_position_slot,
                        "keyStatus": SLOT_STATUS_KEY_PRESENT_WRONG_SLOT,
                        "keyTakenAtTime": datetime.now(TZ_INDIA),
                    }
                )
                session.commit()

                eventDesc = get_event_description(
                    session, EVENT_KEY_RETURNED_WRONG_SLOT
                )

                ams_event_log = AMS_Event_Log(
                    userId=user_auth["id"],
                    keyId=key_record.id,
                    activityId=None,
                    eventId=EVENT_KEY_RETURNED_WRONG_SLOT,
                    loginType="PIN",
                    access_log_id=ams_access_log.id,
                    timeStamp=datetime.now(TZ_INDIA),
                    event_type=EVENT_TYPE_EVENT,
                    eventDesc=eventDesc,
                    is_posted=0,
                )
                session.add(ams_event_log)
                session.commit()

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
                    msg_line1 = "Wrong slot  " + str(current_key_POS)
                    msg_line2 = "Put in slot " + str(correct_key_POS)
                    lcd.lcd_string(msg_line1, lcd.LCD_LINE_1)
                    lcd.lcd_string(msg_line2, lcd.LCD_LINE_2)

                    if key_record.id not in keys_returned_list:
                        keys_returned_list.append(key_record.id)
                    if key_record.id in keys_taken_list:
                        keys_taken_list.remove(key_record.id)
                else:
                    msg_line1 = "Key in wrong pos"
                    lcd.clear_display()
                    sleep(0.1)
                    lcd.lcd_string(msg_line1, lcd.LCD_LINE_1)

                IS_KEY_IN_WRONG_SLOT_Correct_Strip = key_record.keyStrip
                IS_KEY_IN_WRONG_SLOT_Correct_Pos = key_record.keyPosition
                IS_KEY_IN_WRONG_SLOT_Wrong_Strip = ams_can2.key_inserted_position_list
                IS_KEY_IN_WRONG_SLOT_Wrong_Pos = ams_can2.key_inserted_position_slot
                IS_KEY_IN_WRONG_SLOT_User_PIN = None
                BUZZ.write(1)
                sleep(0.5)
                BUZZ.write(0)
                if key_record.keyName not in keys_returned_list:
                    keys_returned_list.append(key_record.keyName)

        else:
            msg_line1 = "Key record n/a  "
            msg_line2 = "Register the key"
            lcd.clear_display()

            lcd.lcd_string(msg_line1, lcd.LCD_LINE_1)
            lcd.lcd_string(msg_line2, lcd.LCD_LINE_2)
            sleep(1)

    counter += 1
    sleep(0.2)
    if counter % 25 == 0:
        lcd.lcd_string("You Can Close", lcd.LCD_LINE_1)
        lcd.lcd_string("   Door Now  ", lcd.LCD_LINE_2)

    return keys_taken_list, keys_returned_list
