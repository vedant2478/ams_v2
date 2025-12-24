from time import sleep
import time
import can
import ctypes

# ----------------- CONSTANTS -----------------
CHANNEL_NAME = "can0"
CAN_SOURCE_MASK = 0x0ff00000
CAN_DESTINATION_MASK = 0x000ff000
CAN_MSG_TYPE_MASK = 0x00000e00
CAN_FUNCTION_MASK = 0x000001ff
CAN_KEY_POSITION_MASK = 0x00f

CAN_MSG_TYPE_ACK = 0
CAN_MSG_TYPE_SET = 1
CAN_MSG_TYPE_GET = 2
CAN_MSG_TYPE_RESPONSE = 3
CAN_MSG_TYPE_BOOTLOADER = 4

CAN_DEVICE_WITHOUT_ID = 0
CAN_DEVICE_DOOR_CONTROL_START_ID = 0x80
CAN_IMX_ID = 0xFE

CAN_FUNCTION_NEW_DEVICE = 0x001
CAN_FUNCTION_VERSION = 0x002
CAN_FUNCTION_SINGLE_LED = 0x003
CAN_FUNCTION_ALL_LEDS = 0x004
CAN_FUNCTION_SINGLE_KEYLOCK = 0x005
CAN_FUNCTION_ALL_KEYLOCKS = 0x006
CAN_FUNCTION_BOXLOCK = 0x007
CAN_FUNCTION_BOX_DOOR_SENSOR = 0x008
CAN_FUNCTION_UNIQUE_ID = 0x00e
CAN_FUNCTION_KEY_ID = 0x040
CAN_FUNCTION_KEY_TAKEN = 0x080
CAN_FUNCTION_KEY_INSERTED = 0x100

CAN_DEVICE_TYPE_KEYLIST = 1
CAN_DEVICE_TYPE_LOCKABLE_KEYLIST = 2

CAN_LED_STATE_OFF = 0
CAN_LED_STATE_ON = 1
CAN_LED_STATE_BLINK = 2

CAN_KEY_LOCKED = 0
CAN_KEY_UNLOCKED = 1

CAN_AMS_DOOR_CLOSED = 0
CAN_AMS_DOOR_OPEN = 1


def _get_message(msg):
    return msg


class AMS_CAN(object):
    def __init__(self):
        self._channel_name = CHANNEL_NAME
        self._can_controller_id = CAN_IMX_ID
        self._Is_initialized = False
        self._current_function = None
        self._current_function_list_id = None
        self._current_function_ack = False
        self._current_function_response = False
        self._current_function_response_data = None

        # key events
        self.key_inserted_event = False
        self.key_inserted_id = None
        self.key_taken_event = False
        self.key_taken_id = None
        self.key_inserted_position_slot = None
        self.key_taken_position_slot = None
        self.key_inserted_position_list = None
        self.key_taken_position_list = None

        self.key_lists = []
        self.key_lists_version = {}

        # CAN bus (python-can)
        self.bus = can.Bus(channel="can0", interface="socketcan", bitrate=125000)

        # listener + notifier
        self.buffer = can.BufferedReader()
        self.buffer.on_message_received = self._on_message_received
        self.notifier = can.Notifier(self.bus, [_get_message, self.buffer])

        # Optional door lock shared library
        try:
            print("Loading libKeyStrip.so...")
            self.lib_door_lock = ctypes.CDLL("libKeyStrip.so")
            self.lib_door_lock.canInit.argtypes = []
            print("Calling canInit...")
            self.Lock_FD = self.lib_door_lock.canInit()
            print("Door lock init done, fd =", self.Lock_FD)
            sleep(2)
        except OSError as e:
            print("Warning: door lock lib not usable, skipping:", e)
            self.lib_door_lock = None
            self.Lock_FD = None

    # ---------- Low-level CAN helpers ----------

    def create_arbitration_id(self, source, destination, message_type, function):
        arbitration_id = 0x0
        arbitration_id |= ((source & 0xff) << 20)
        arbitration_id |= ((destination & 0xff) << 12)
        arbitration_id |= ((message_type & 0x7) << 9)
        arbitration_id |= (function & CAN_FUNCTION_MASK)
        return arbitration_id

    def send_message(self, message):
        try:
            self.bus.send(message)
            return True
        except can.CanError:
            print("message not sent!")
            return False

    def _on_message_received(self, msg):
        source_list = (msg.arbitration_id & CAN_SOURCE_MASK) >> 20
        destination = (msg.arbitration_id & CAN_DESTINATION_MASK) >> 12
        message_type = (msg.arbitration_id & CAN_MSG_TYPE_MASK) >> 9
        function_type = msg.arbitration_id & CAN_FUNCTION_MASK

        # --- INITIAL HANDSHAKE / DISCOVERY ---
        if (
            source_list == 0
            and function_type == CAN_FUNCTION_UNIQUE_ID
            and destination == CAN_IMX_ID
        ):
            # UNIQUE_ID received: send ACK
            print("\nINIT--RECV--[1]: LIST -> IMX - UNIQUE ID Message Received")
            arb_id = self.create_arbitration_id(
                CAN_IMX_ID, 0x0, CAN_MSG_TYPE_ACK, CAN_FUNCTION_UNIQUE_ID
            )
            msg_ack = can.Message(
                arbitration_id=arb_id, data=[], is_extended_id=True
            )
            self._current_function = CAN_FUNCTION_UNIQUE_ID
            self._current_function_ack = True
            self._current_function_response = False
            self._current_function_response_data = None
            self.send_message(msg_ack)
            sleep(0.6)

            # assign new device id
            arb_id = self.create_arbitration_id(
                CAN_IMX_ID, 0x0, CAN_MSG_TYPE_SET, CAN_FUNCTION_NEW_DEVICE
            )
            new_device_id = len(self.key_lists) + 1
            self.key_lists.append(new_device_id)
            msg_set = can.Message(
                arbitration_id=arb_id,
                data=[new_device_id],
                is_extended_id=True,
            )
            self._current_function = CAN_FUNCTION_NEW_DEVICE
            self._current_function_list_id = new_device_id
            self._current_function_ack = True
            self._current_function_response = False
            self._current_function_response_data = None
            self.send_message(msg_set)
            sleep(0.6)
            print(
                "\nINIT--SENT--[3]: IMS -> LIST - DEVICE ID message sent 1st Time [LIST Id - "
                + str(new_device_id)
            )

        if (
            source_list == 0
            and function_type == CAN_FUNCTION_NEW_DEVICE
            and message_type == CAN_MSG_TYPE_ACK
        ):
            self._current_function = CAN_FUNCTION_NEW_DEVICE
            self._current_function_list_id = source_list
            print(
                "\nINIT--RECV--[4]: LIST -> IMS - ACK for DEVICE ID message received from LIST [LIST Id - "
                + str(source_list)
            )

        if (
            source_list != 0
            and function_type == CAN_FUNCTION_NEW_DEVICE
            and message_type == CAN_MSG_TYPE_GET
        ):
            # List asks again for its device id
            arb_id = self.create_arbitration_id(
                CAN_IMX_ID, source_list, CAN_MSG_TYPE_ACK, CAN_FUNCTION_NEW_DEVICE
            )
            msg_ack = can.Message(
                arbitration_id=arb_id,
                data=[],
                is_extended_id=True,
            )
            self._current_function = CAN_FUNCTION_NEW_DEVICE
            self._current_function_list_id = source_list
            self._current_function_ack = False
            self._current_function_response = True
            self._current_function_response_data = None
            self.send_message(msg_ack)
            sleep(0.6)

        if (
            source_list != 0
            and function_type == CAN_FUNCTION_NEW_DEVICE
            and message_type == CAN_MSG_TYPE_ACK
        ):
            print(
                "\nINIT--RECV--[7]: LIST -> IMX - ACK received from LIST for 2nd DEVICE ID message [LIST Id - "
                + str(source_list)
            )
            self._current_function = None
            self._current_function_list_id = source_list
            self._current_function_ack = True
            self._current_function_response = False
            self._current_function_response_data = None

        # --- NORMAL COMMAND RESPONSES / KEY EVENTS ---
        if (
            destination == CAN_IMX_ID
            and function_type != CAN_FUNCTION_NEW_DEVICE
            and function_type != CAN_FUNCTION_UNIQUE_ID
        ):
            # ACK for current function
            if (
                message_type == CAN_MSG_TYPE_ACK
                and function_type == self._current_function
            ):
                self._current_function_ack = True
                self._current_function_response = True

            # RESPONSE payload for current function
            elif (
                message_type == CAN_MSG_TYPE_RESPONSE
                and function_type == self._current_function
            ):
                self._current_function_response = True
                self._current_function_response_data = msg.data
                if function_type == CAN_FUNCTION_VERSION:
                    if source_list not in self.key_lists:
                        self.key_lists.append(source_list)

            # KEY TAKEN event
            elif (
                message_type == CAN_MSG_TYPE_SET
                and (function_type & 0xF0) == CAN_FUNCTION_KEY_TAKEN
            ):
                self._current_function = CAN_FUNCTION_KEY_TAKEN
                self.key_taken_position_list = source_list
                self.key_taken_position_slot = (function_type & 0xF) + 1
                self._current_function_response = True
                self._current_function_response_data = msg.data
                self.key_taken_event = True
                result_list = list(self._current_function_response_data)
                key_fob_id = "".join(str(num) for num in result_list[:5])
                self.key_taken_id = int(key_fob_id)

            # KEY INSERTED event
            elif (
                message_type == CAN_MSG_TYPE_SET
                and (function_type & 0xFF0) == CAN_FUNCTION_KEY_INSERTED
            ):
                self._current_function = CAN_FUNCTION_KEY_INSERTED
                self.key_inserted_position_list = source_list
                self.key_inserted_position_slot = (function_type & 0xF) + 1
                self._current_function_response = True
                self._current_function_response_data = msg.data
                self.key_inserted_event = True
                result_list = list(self._current_function_response_data)
                key_fob_id = "".join(str(num) for num in result_list[:5])
                self.key_inserted_id = int(key_fob_id)

    # ---------- High-level CAN API ----------

    def get_version_number(self, list_ID):
        arb_id = self.create_arbitration_id(
            self._can_controller_id,
            list_ID,
            CAN_MSG_TYPE_GET,
            CAN_FUNCTION_VERSION,
        )
        msg = can.Message(
            arbitration_id=arb_id, data=[], is_extended_id=True
        )
        self._current_function = CAN_FUNCTION_VERSION
        self._current_function_list_id = list_ID
        self._current_function_ack = False
        self._current_function_response = False
        self._current_function_response_data = ""
        self.send_message(msg)
        sleep(0.5)
        if self._current_function_response and self._current_function_response_data:
            return list(self._current_function_response_data)
        else:
            return None

    def set_all_LED_ON(self, list_ID, blinking):
        arb_id = self.create_arbitration_id(
            self._can_controller_id,
            list_ID,
            CAN_MSG_TYPE_SET,
            CAN_FUNCTION_ALL_LEDS,
        )
        data = [0x22] * 7 if blinking else [0x11] * 7
        msg = can.Message(
            arbitration_id=arb_id, data=data, is_extended_id=True
        )
        self._current_function = CAN_FUNCTION_ALL_LEDS
        self._current_function_list_id = list_ID
        self._current_function_ack = False
        self._current_function_response = False
        self._current_function_response_data = None
        self.send_message(msg)
        sleep(0.1)
        return bool(self._current_function_response)

    def set_all_LED_OFF(self, list_ID):
        arb_id = self.create_arbitration_id(
            self._can_controller_id,
            list_ID,
            CAN_MSG_TYPE_SET,
            CAN_FUNCTION_ALL_LEDS,
        )
        msg = can.Message(
            arbitration_id=arb_id,
            data=[0x00] * 7,
            is_extended_id=True,
        )
        self._current_function = CAN_FUNCTION_ALL_LEDS
        self._current_function_list_id = list_ID
        self._current_function_ack = False
        self._current_function_response = False
        self._current_function_response_data = None
        self.send_message(msg)
        sleep(0.1)
        return bool(self._current_function_response)

    def set_single_LED_state(self, list_ID, led_ID, led_state):
        arb_id = self.create_arbitration_id(
            self._can_controller_id,
            list_ID,
            CAN_MSG_TYPE_SET,
            CAN_FUNCTION_SINGLE_LED,
        )
        msg = can.Message(
            arbitration_id=arb_id,
            data=[led_ID, led_state],
            is_extended_id=True,
        )
        self._current_function = CAN_FUNCTION_SINGLE_LED
        self._current_function_list_id = list_ID
        self._current_function_ack = False
        self._current_function_response = False
        self._current_function_response_data = None
        self.send_message(msg)
        sleep(0.1)
        return bool(self._current_function_response)

    def set_single_key_lock_state(self, list_ID, position, lock_status):
        arb_id = self.create_arbitration_id(
            self._can_controller_id,
            list_ID,
            CAN_MSG_TYPE_SET,
            CAN_FUNCTION_SINGLE_KEYLOCK,
        )
        msg = can.Message(
            arbitration_id=arb_id,
            data=[position, lock_status],
            is_extended_id=True,
        )
        self._current_function = CAN_FUNCTION_SINGLE_KEYLOCK
        self._current_function_list_id = list_ID
        self._current_function_ack = False
        self._current_function_response = False
        self._current_function_response_data = None
        self.send_message(msg)
        sleep(0.1)
        return bool(self._current_function_response)

    def lock_all_positions(self, list_ID):
        arb_id = self.create_arbitration_id(
            self._can_controller_id,
            list_ID,
            CAN_MSG_TYPE_SET,
            CAN_FUNCTION_ALL_KEYLOCKS,
        )
        msg = can.Message(
            arbitration_id=arb_id,
            data=[0x00] * 7,
            is_extended_id=True,
        )
        self._current_function = CAN_FUNCTION_ALL_KEYLOCKS
        self._current_function_list_id = list_ID
        self._current_function_ack = False
        self._current_function_response = False
        self._current_function_response_data = None
        self.send_message(msg)
        sleep(0.1)
        return bool(self._current_function_response)

    def unlock_all_positions(self, list_ID):
        arb_id = self.create_arbitration_id(
            self._can_controller_id,
            list_ID,
            CAN_MSG_TYPE_SET,
            CAN_FUNCTION_ALL_KEYLOCKS,
        )
        msg = can.Message(
            arbitration_id=arb_id,
            data=[0x11] * 7,
            is_extended_id=True,
        )
        self._current_function = CAN_FUNCTION_ALL_KEYLOCKS
        self._current_function_list_id = list_ID
        self._current_function_ack = False
        self._current_function_response = False
        self._current_function_response_data = None
        self.send_message(msg)
        sleep(0.1)
        return bool(self._current_function_response)

    def cleanup(self):
        self.notifier.stop()
        self.bus.shutdown()


# ----------------- MAIN SINGLE-FILE LOGIC -----------------

def main():
    print("Starting AMS CAN single-file tool...")
    ams_can = AMS_CAN()
    sleep(6)

    # Optional: read versions for first two lists if present
    print("Trying to read version from list 1 & 2 (if they exist)...")
    for lid in (1, 2):
        v = ams_can.get_version_number(lid)
        if v:
            print(f"Keystrip {lid} version: {v}")

    # Discover keylists during initial CAN traffic
    sleep(2)
    print("Detected keylists:", ams_can.key_lists)

    # Lock everything and turn LEDs off initially
    for list_id in ams_can.key_lists:
        ams_can.lock_all_positions(list_id)
        ams_can.set_all_LED_OFF(list_id)

    try:
        while True:
            print("\n=== Unlock a key position ===")
            if not ams_can.key_lists:
                print("No keylists detected yet. Waiting 5 seconds...")
                sleep(5)
                print("Detected keylists:", ams_can.key_lists)
                continue

            print("Available keystrips:", ams_can.key_lists)
            try:
                list_id = int(input("Enter keystrip (list) ID: ").strip())
                slot = int(input("Enter pin/slot number to unlock (1-14): ").strip())
            except ValueError:
                print("Invalid input, please enter numbers only.")
                continue

            if list_id not in ams_can.key_lists:
                print(f"List {list_id} not in detected keylists.")
                continue
            if not (1 <= slot <= 14):
                print("Slot must be between 1 and 14.")
                continue

            print(f"Unlocking strip {list_id}, slot {slot}...")
            led_ok = ams_can.set_single_LED_state(list_id, slot, CAN_LED_STATE_ON)
            lock_ok = ams_can.set_single_key_lock_state(list_id, slot, CAN_KEY_UNLOCKED)
            print(f"LED set: {led_ok}, lock unlocked: {lock_ok}")

            # small pause so user sees effect
            sleep(1)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        ams_can.cleanup()


if __name__ == "__main__":
    main()
