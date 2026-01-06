from time import sleep
import can

# =========================================================
# CONSTANTS (UNCHANGED)
# =========================================================
CHANNEL_NAME = "can0"

CAN_SOURCE_MASK = 0x0FF00000
CAN_DESTINATION_MASK = 0x000FF000
CAN_MSG_TYPE_MASK = 0x00000E00
CAN_FUNCTION_MASK = 0x000001FF

CAN_MSG_TYPE_ACK = 0
CAN_MSG_TYPE_SET = 1
CAN_MSG_TYPE_GET = 2
CAN_MSG_TYPE_RESPONSE = 3

CAN_IMX_ID = 0xFE

CAN_FUNCTION_NEW_DEVICE = 0x001
CAN_FUNCTION_VERSION = 0x002
CAN_FUNCTION_SINGLE_LED = 0x003
CAN_FUNCTION_ALL_LEDS = 0x004
CAN_FUNCTION_SINGLE_KEYLOCK = 0x005
CAN_FUNCTION_ALL_KEYLOCKS = 0x006
CAN_FUNCTION_UNIQUE_ID = 0x00E
CAN_FUNCTION_KEY_ID = 0x040
CAN_FUNCTION_KEY_TAKEN = 0x080
CAN_FUNCTION_KEY_INSERTED = 0x100

CAN_LED_STATE_OFF = 0
CAN_LED_STATE_ON = 1
CAN_LED_STATE_BLINK = 2

CAN_KEY_LOCKED = 0
CAN_KEY_UNLOCKED = 1


def _get_message(msg):
    return msg


# =========================================================
# AMS CAN CLASS (FIXED)
# =========================================================
class AMS_CAN:
    def __init__(self):
        self._can_controller_id = CAN_IMX_ID

        self.bus = can.Bus(
            channel=CHANNEL_NAME,
            bustype="socketcan",
            bitrate=125000,
        )

        self.buffer = can.BufferedReader()
        self.buffer.on_message_received = self._on_message_received

        self.notifier = None
        self._listening = False

        # ---- Runtime State ----
        self.key_lists = []

        self.key_taken_event = False
        self.key_taken_id = None
        self.key_inserted_event = False
        self.key_inserted_id = None

        self._current_function = None
        self._current_function_response = False
        self._current_function_response_data = None

    # =====================================================
    # 🔴 LISTENER CONTROL (CRITICAL FIX)
    # =====================================================
    def start_listener(self):
        if self._listening:
            return

        self.notifier = can.Notifier(
            self.bus,
            [_get_message, self.buffer],
        )
        self._listening = True
        print("[AMS_CAN] Listener started")

    def stop_listener(self):
        if not self._listening:
            return

        if self.notifier:
            self.notifier.stop()
            self.notifier = None

        self.flush_buffer()
        self._listening = False
        print("[AMS_CAN] Listener stopped")

    # =====================================================
    # MESSAGE HANDLER
    # =====================================================
    def _on_message_received(self, msg):
        source = (msg.arbitration_id & CAN_SOURCE_MASK) >> 20
        destination = (msg.arbitration_id & CAN_DESTINATION_MASK) >> 12
        msg_type = (msg.arbitration_id & CAN_MSG_TYPE_MASK) >> 9
        function = msg.arbitration_id & CAN_FUNCTION_MASK

        # ---- DEVICE DISCOVERY ----
        if source == 0 and function == CAN_FUNCTION_UNIQUE_ID:
            new_id = len(self.key_lists) + 1
            if new_id not in self.key_lists:
                self.key_lists.append(new_id)

        # ---- KEY TAKEN ----
        if msg_type == CAN_MSG_TYPE_SET and (function & 0xF0) == CAN_FUNCTION_KEY_TAKEN:
            self.key_taken_event = True
            self.key_taken_id = self._decode_key_id(msg.data)

        # ---- KEY INSERTED ----
        if msg_type == CAN_MSG_TYPE_SET and (function & 0xFF0) == CAN_FUNCTION_KEY_INSERTED:
            self.key_inserted_event = True
            self.key_inserted_id = self._decode_key_id(msg.data)

    def _decode_key_id(self, data):
        key_id = 0
        for b in list(data)[:5]:
            key_id = (key_id << 8) | b
        return key_id

    # =====================================================
    # SEND HELPERS
    # =====================================================
    def create_arbitration_id(self, src, dst, msg_type, function):
        return (
            (src & 0xFF) << 20
            | (dst & 0xFF) << 12
            | (msg_type & 0x7) << 9
            | (function & CAN_FUNCTION_MASK)
        )

    def send_message(self, msg):
        try:
            self.bus.send(msg)
            return True
        except can.CanError:
            print("[AMS_CAN] Message send failed")
            return False

    # =====================================================
    # PUBLIC API (UNCHANGED)
    # =====================================================
    def unlock_single_key(self, strip, pos):
        self.start_listener()
        self.set_single_LED_state(strip, pos, CAN_LED_STATE_ON)
        self.set_single_key_lock_state(strip, pos, CAN_KEY_UNLOCKED)

    def set_single_LED_state(self, strip, pos, state):
        arb = self.create_arbitration_id(
            self._can_controller_id, strip, CAN_MSG_TYPE_SET, CAN_FUNCTION_SINGLE_LED
        )
        self.send_message(
            can.Message(arbitration_id=arb, data=[pos, state], is_extended_id=True)
        )
        sleep(0.15)

    def set_single_key_lock_state(self, strip, pos, state):
        arb = self.create_arbitration_id(
            self._can_controller_id, strip, CAN_MSG_TYPE_SET, CAN_FUNCTION_SINGLE_KEYLOCK
        )
        self.send_message(
            can.Message(arbitration_id=arb, data=[pos, state], is_extended_id=True)
        )
        sleep(0.15)

    def lock_all_positions(self, strip):
        arb = self.create_arbitration_id(
            self._can_controller_id, strip, CAN_MSG_TYPE_SET, CAN_FUNCTION_ALL_KEYLOCKS
        )
        self.send_message(
            can.Message(arbitration_id=arb, data=[0x00] * 7, is_extended_id=True)
        )
        sleep(0.2)

    def unlock_all_positions(self, strip):
        arb = self.create_arbitration_id(
            self._can_controller_id, strip, CAN_MSG_TYPE_SET, CAN_FUNCTION_ALL_KEYLOCKS
        )
        self.send_message(
            can.Message(arbitration_id=arb, data=[0x11] * 7, is_extended_id=True)
        )
        sleep(0.2)

    # =====================================================
    # BUFFER + CLEANUP
    # =====================================================
    def flush_buffer(self):
        while self.buffer.get_message():
            pass

    def cleanup(self):
        print("[AMS_CAN] Cleanup")
        self.stop_listener()
        self.bus.shutdown()


# =========================================================
# TEST MAIN
# =========================================================
def main():
    ams_can = AMS_CAN()

    ams_can.start_listener()
    sleep(5)

    print("Keylists:", ams_can.key_lists)

    ams_can.unlock_all_positions(1)
    sleep(2)
    ams_can.lock_all_positions(1)

    ams_can.cleanup()


if __name__ == "__main__":
    main()
