import sys
# import mraa   # ❌ COMMENTED
import threading
from . import bms
from csi_ams.model import *
from csi_ams.amscan import *
import _thread as thread
from datetime import datetime
from csi_ams.utils import lcd, keypad, card_reader
import pytz
from time import sleep

# ================= AUTH CONSTANTS =================
AUTH_MODE_PIN = 1
AUTH_MODE_CARD = 2

AUTH_RESULT_SUCCESS = 0
AUTH_RESULT_FAILED = 1

# ================= ACTIVITY CONSTANTS =================
ACTIVITY_ALLOWED = 0
ACTIVITY_ERROR_USER_INVALID = 1
ACTIVITY_ERROR_TIME_INVALID = 2
ACTIVITY_ERROR_WEEKDAY_INVALID = 3
ACTIVITY_ERROR_FREQUENCY_EXCEEDED = 4
ACTIVITY_ERROR_CODE_INCORRECT = 5

# ================= EVENT CONSTANTS =================
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

# ================= SLOT STATUS =================
SLOT_STATUS_KEY_NOT_PRESENT = 0
SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT = 1
SLOT_STATUS_KEY_PRESENT_WRONG_SLOT = 2

# ================= GPIO CONSTANTS (COMMENTED) =================
# BUZZER_PIN = 37
# DOOR_LOCK_PIN = 40
# LIMIT_SWITCH_PIN = 32

# BUZZ = mraa.Gpio(BUZZER_PIN)
# DOOR_LOCK = mraa.Gpio(DOOR_LOCK_PIN)
# LIMIT_SWITCH = mraa.Gpio(LIMIT_SWITCH_PIN)

# DOOR_LOCK.dir(mraa.DIR_OUT)
# BUZZ.dir(mraa.DIR_OUT)
# LIMIT_SWITCH.dir(mraa.DIR_IN)

# ================= TIMEZONE =================
TZ_INDIA = pytz.timezone("Asia/Kolkata")
CABINET_SHUTDOWN_INT = 7

key_pad = keypad.MyKeyboard()
counter = 0

# ================= DB =================
SQLALCHEMY_DATABASE_URI = (
    "sqlite:////home/rock/Desktop/ams_v2/csiams.dev.sqlite"
)

# ================= HELPERS =================
def quit_function(fn_name):
    print(f"inside function {fn_name}")
    print("\n\tTIMEOUT!!! Press any key", file=sys.stderr)
    thread.interrupt_main()


def exit_after(s):
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
def login_using_PIN(session, lcd, key_pad, line=lcd.LCD_LINE_2):
    pin_char_count = 0
    pin_entered = ""
    while pin_char_count < 5:
        key = take_key_pad_input(session, key_pad)
        if key is not None:
            if key.isnumeric():
                pin_entered += key
                lcd.lcd_string("*" * len(pin_entered), line)
                pin_char_count += 1
            elif key == "#":
                return AUTH_MODE_PIN, pin_entered
    return AUTH_MODE_PIN, pin_entered


@exit_after(60)
def login_using_PIN_Card(lcd, key_pad, session):
    lcd.clear_display()
    lcd.lcd_string("Login Option", lcd.LCD_LINE_1)
    lcd.lcd_string("1. Card   2. Pin", lcd.LCD_LINE_2)

    login_option = take_key_pad_input(session, key_pad)

    if login_option == "1":
        lcd.clear_display()
        lcd.lcd_string("Swipe your card ...", lcd.LCD_LINE_1)

        time_sec = 0
        Card_No = 0
        while True:
            Card_No = int(card_reader.get_card_no(card_reader.ser))
            if Card_No > 0 or time_sec >= 15:
                break
            time_sec += 1

        return AUTH_MODE_CARD, Card_No

    elif login_option == "2":
        lcd.clear_display()
        lcd.lcd_string("Enter PIN:", lcd.LCD_LINE_1)
        return login_using_PIN(session, lcd, key_pad)

    lcd.clear_display()
    lcd.lcd_string("Wrong Input", lcd.LCD_LINE_1)
    sleep(2)
    return -1, 0


def show_ideal_msg(lcd, cabinet):
    BATTERY_CHARGE_PC = str(bms.get_batt_pct(bms.ser))
    lcd.lcd_string(f"HPCL KMS    {BATTERY_CHARGE_PC}%", lcd.LCD_LINE_1)
    lcd.lcd_string(f"RO CODE:{cabinet.site.siteName}", lcd.LCD_LINE_2)


def read_limit_switch(_):
    # GPIO disabled → always closed
    return 0


def take_key_pad_input(session, key_pad):
    key_str = None
    while key_str is None:
        key_str = key_pad.ReadKey()
    return key_str

def get_event_description(session, event_status):
    """
    Fetch event description from DB using event ID
    """
    event_type = (
        session.query(AMS_Event_Types)
        .filter(AMS_Event_Types.eventId == event_status)
        .one_or_none()
    )

    if event_type:
        return event_type.eventDescription

    return ""
