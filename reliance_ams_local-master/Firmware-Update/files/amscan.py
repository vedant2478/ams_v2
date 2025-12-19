from time import sleep
import can
import ctypes
import logging

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
        self.bus = can.Bus(channel="can0", bustype="socketcan", bitrate=125000)

        self.buffer = can.BufferedReader()
        self.buffer.on_message_received = self._on_message_received
        self.notifier = can.Notifier(self.bus, [_get_message, self.buffer])

        # Cabinet DOOR LOCK management - REPLACE BELOW WITH ACTUAL LIB FUNCTIONS
        self.lib_door_lock = ctypes.CDLL("libKeyStrip.so")
        self.lib_door_lock.canInit.argtypes = []
        self.Lock_FD = self.lib_door_lock.canInit()
        sleep(2)
        # self.lib_door_lock.setKeyBoxLock.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        # self.lib_door_lock.setKeyBoxLock(self.Lock_FD, 1, 1, 0)
        # self.door_closed_status = True


    def create_arbitration_id(self, source, destination, message_type, function):
        arbitration_id = 0x0
        arbitration_id |= ((source & 0xff) << 20)
        arbitration_id |= ((destination & 0xff) << 12)
        arbitration_id |= ((message_type & 0x7) << 9)
        arbitration_id |= (function & CAN_FUNCTION_MASK)
        return arbitration_id

    def _on_message_received(self, msg):
        # print("\nCAN MESSAGE RECEIVED : " + str(msg))
        source_list = ((msg.arbitration_id & CAN_SOURCE_MASK) >> 20)
        destination = ((msg.arbitration_id & CAN_DESTINATION_MASK) >> 12)
        message_type = (msg.arbitration_id & CAN_MSG_TYPE_MASK) >> 9
        function_type = (msg.arbitration_id & CAN_FUNCTION_MASK)
        # print("\nSource = " + str(source_list) + " Destination = " + str(destination) + " Function Type : " + str(function_type))
        # print("\n Data received : " + str(msg.data))
        # INIT PROCEDURE - Process query from Key-List(s) and send ACK
        new_device_id = 0
        if source_list == 0 and function_type == CAN_FUNCTION_UNIQUE_ID and destination == CAN_IMX_ID:
            # Send ACK to UNIQUE ID message
            print("\nINIT--RECV--[1]: LIST -> IMX - UNIQUE ID Message Received")
            arb_id = self.create_arbitration_id(CAN_IMX_ID, 0x0, CAN_MSG_TYPE_ACK,
                                                CAN_FUNCTION_UNIQUE_ID)

            msg = can.Message(arbitration_id=arb_id,
                              data=[],
                              is_extended_id=True)
            self._current_function = CAN_FUNCTION_UNIQUE_ID
            self._current_function_ack = True
            self._current_function_response = False
            self._current_function_response_data = None
            self.send_message(msg)
            sleep(0.5)
            print("\nINIT--SENT--[2]: IMS -> LIST - ACK message sent to UNIQUE ID Message")
            #print("\nINIT[2]: IMS -> LIS UNIQUE ID ACK")

            # Send device id to list

            arb_id = self.create_arbitration_id(CAN_IMX_ID, 0x0, CAN_MSG_TYPE_SET,
                                                CAN_FUNCTION_NEW_DEVICE)

            new_device_id = len(self.key_lists) + 1
            self.key_lists.append(new_device_id)
            msg = can.Message(arbitration_id=arb_id,
                              data=[new_device_id],
                              is_extended_id=True)
            self._current_function = CAN_FUNCTION_NEW_DEVICE
            self._current_function_list_id = new_device_id
            self._current_function_ack = True
            self._current_function_response = False
            self._current_function_response_data = None
            self.send_message(msg)
            sleep(0.5)
            print("\nINIT--SENT--[3]: IMS -> LIST - DEVICE ID message sent 1st Time [LIST Id - " + str(new_device_id))

        if source_list == 0 and function_type == CAN_FUNCTION_NEW_DEVICE and message_type == CAN_MSG_TYPE_ACK:
            self._current_function = CAN_FUNCTION_NEW_DEVICE
            self._current_function_list_id = source_list
            print("\nINIT--RECV--[4]: LIST -> IMS - ACK for DEVICE ID message received from LIST [LIST Id - " + str(source_list))
        if source_list != 0 and function_type == CAN_FUNCTION_NEW_DEVICE and message_type == CAN_MSG_TYPE_GET:
            #print("\nINIT--[6]: LIST -> IMS - DEVICE ID message received from LIST")
            #print("\nINIT[4]: LIST -> IMX NEW DEVICE ACK")
            # Send ACK to List
            arb_id = self.create_arbitration_id(CAN_IMX_ID, source_list, CAN_MSG_TYPE_ACK,
                                                CAN_FUNCTION_NEW_DEVICE)
            msg = can.Message(arbitration_id=arb_id,
                              data=[],
                              is_extended_id=True)
            self._current_function = CAN_FUNCTION_NEW_DEVICE
            self._current_function_list_id = source_list
            self._current_function_ack = True
            self._current_function_response = False
            self._current_function_response_data = None
            self.send_message(msg)
            print("\nINIT--SENT--[5]: IMX -> ACK message to LIST [LIST ID - " + str(source_list))
            sleep(0.5)
            
            # Send device id to list - 2nd time
            arb_id = self.create_arbitration_id(CAN_IMX_ID, source_list, CAN_MSG_TYPE_SET,
                                                CAN_FUNCTION_NEW_DEVICE)

            msg = can.Message(arbitration_id=arb_id,
                              data=[source_list],
                              is_extended_id=True)
            
            self._current_function = CAN_FUNCTION_NEW_DEVICE
            self._current_function_list_id = source_list
            self._current_function_ack = False
            self._current_function_response = True
            self._current_function_response_data = None
            self.send_message(msg)
            sleep(0.5)
            print("\nINIT--SENT--[6]: IMX -> LIST - ACK for LIST DEVICE ID message sent [LIST Id - " + str(source_list))
            #print("\nINIT[6]: IMX -> LIST NEW DEVICE SET MSG")

        # INIT PROCEDURE - Process response from Key-List and add the list to AMS-CAN key-list[]
        if source_list != 0 and  function_type == CAN_FUNCTION_NEW_DEVICE and message_type == CAN_MSG_TYPE_ACK:
            print("\nINIT--RECV--[7]: LIST -> IMX - ACK  received from LIST for 2nd DEVICE ID message [LIST Id - " + str(source_list))

            # if source_list not in self.key_lists:
            #     self.key_lists.append(source_list)
            #     print("********* Adding " + str(source_list) + " to keylist having current length of " + str(len(self.key_lists)))
            self._current_function = None
            self._current_function_list_id = source_list
            self._current_function_ack = True
            self._current_function_response = False
            self._current_function_response_data = None

        if destination == CAN_IMX_ID and function_type != CAN_FUNCTION_NEW_DEVICE and function_type != CAN_FUNCTION_UNIQUE_ID:
            print("##### Inside command on_message")
            if message_type == CAN_MSG_TYPE_ACK and function_type == self._current_function:
                self._current_function_ack = True
                self._current_function_response = True
            elif message_type == CAN_MSG_TYPE_RESPONSE and function_type == self._current_function:
                self._current_function_response = True
                self._current_function_response_data = msg.data
                if function_type == CAN_FUNCTION_VERSION:
                    if source_list not in self.key_lists:
                        self.key_lists.append(source_list)
            elif message_type == CAN_MSG_TYPE_SET and (function_type & 0xF0) == CAN_FUNCTION_KEY_TAKEN:
                self._current_function = CAN_FUNCTION_KEY_TAKEN
                self.key_taken_position_list = source_list
                self.key_taken_position_slot = (function_type & 0xF) + 1
                #print("#### Key taken from slot no: " + str(self.key_taken_position_slot))
                self._current_function_response = True
                self._current_function_response_data = msg.data
                self.key_taken_event = True
                result_list = list(self._current_function_response_data)
                key_fob_id=''
                for num in result_list[:5]:
                    key_fob_id += str(num)
                self.key_taken_id = int(key_fob_id)

            elif message_type == CAN_MSG_TYPE_SET and (function_type & 0xFF0) == CAN_FUNCTION_KEY_INSERTED:
                self._current_function = CAN_FUNCTION_KEY_INSERTED
                self.key_inserted_position_list = source_list
                self.key_inserted_position_slot = (function_type & 0xF) + 1
                #print("#### Key inserted at slot no: " + str(self.key_inserted_position_slot))
                self._current_function_response = True
                self._current_function_response_data = msg.data
                self.key_inserted_event = True
                result_list = list(self._current_function_response_data)
                key_fob_id = ''
                for num in result_list[:5]:
                    key_fob_id += str(num)
                self.key_inserted_id = int(key_fob_id)


    def get_version_number(self, list_ID):
        arb_id = self.create_arbitration_id(self._can_controller_id, list_ID, CAN_MSG_TYPE_GET,
                                            CAN_FUNCTION_VERSION)
        msg = can.Message(arbitration_id=arb_id,
                          data=[],
                          is_extended_id=True)
        self._current_function = CAN_FUNCTION_VERSION
        self._current_function_list_id = list_ID
        self._current_function_ack = False
        self._current_function_response = False
        self._current_function_response_data = ''
        self.send_message(msg)
        sleep(0.5)
        print("Get Version no Response: " + str(self._current_function_response) + "   & Date = " + str(self._current_function_response_data))
        if self._current_function_response and self._current_function_response_data:
            return list(self._current_function_response_data)
        else:
            return None

    def set_all_LED_ON(self, list_ID, blinking):

        arb_id = self.create_arbitration_id(self._can_controller_id, list_ID, CAN_MSG_TYPE_SET,
                                            CAN_FUNCTION_ALL_LEDS)

        if blinking:
            msg = can.Message(arbitration_id=arb_id,
                              data=[0x22, 0x22, 0x22, 0x22, 0x22, 0x22, 0x22],
                              is_extended_id=True)
        else:
            msg = can.Message(arbitration_id=arb_id,
                              data=[0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11],
                              is_extended_id=True)

        self._current_function = CAN_FUNCTION_ALL_LEDS
        self._current_function_list_id = list_ID
        self._current_function_ack = False
        self._current_function_response = False
        self._current_function_response_data = None
        self.send_message(msg)
        sleep(0.5)
        if self._current_function_response:
            return True
        else:
            return False

    def set_all_LED_OFF(self, list_ID):

        arb_id = self.create_arbitration_id(self._can_controller_id, list_ID, CAN_MSG_TYPE_SET,
                                            CAN_FUNCTION_ALL_LEDS)

        msg = can.Message(arbitration_id=arb_id,
                          data=[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                          is_extended_id=True)
        self._current_function = CAN_FUNCTION_ALL_LEDS
        self._current_function_list_id = list_ID
        self._current_function_ack = False
        self._current_function_response = False
        self._current_function_response_data = None
        self.send_message(msg)
        sleep(0.5)
        if self._current_function_response:
            return True
        else:
            return False

    # Note that LED/POSITIONS range from 0 to 13
    def set_single_LED_state(self, list_ID, led_ID, led_state):
        arb_id = self.create_arbitration_id(self._can_controller_id, list_ID, CAN_MSG_TYPE_SET,
                                            CAN_FUNCTION_SINGLE_LED)

        msg = can.Message(arbitration_id=arb_id,
                          data=[led_ID, led_state],
                          is_extended_id=True)
        self._current_function = CAN_FUNCTION_SINGLE_LED
        self._current_function_list_id = list_ID
        self._current_function_ack = False
        self._current_function_response = False
        self._current_function_response_data = None
        self.send_message(msg)
        sleep(0.5)
        if self._current_function_response:
            return True
        else:
            return False

    def set_single_key_lock_state(self, list_ID, position, lock_status):
        # print("\n\nParameters received: " + str(position) + " Lock status " + str(lock_status) + "\n")
        arb_id = self.create_arbitration_id(self._can_controller_id, list_ID, CAN_MSG_TYPE_SET,
                                            CAN_FUNCTION_SINGLE_KEYLOCK)

        msg = can.Message(arbitration_id=arb_id,
                          data=[position, lock_status],
                          is_extended_id=True)
        self._current_function = CAN_FUNCTION_SINGLE_KEYLOCK
        self._current_function_list_id = list_ID
        self._current_function_ack = False
        self._current_function_response = False
        self._current_function_response_data = None
        self.send_message(msg)
        sleep(0.5)
        if self._current_function_response:
            return True
        else:
            return False

    def lock_all_positions(self, list_ID):
        arb_id = self.create_arbitration_id(self._can_controller_id, list_ID, CAN_MSG_TYPE_SET,
                                            CAN_FUNCTION_ALL_KEYLOCKS)

        msg = can.Message(arbitration_id=arb_id,
                          data=[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                          is_extended_id=True)
        self._current_function = CAN_FUNCTION_ALL_KEYLOCKS
        self._current_function_list_id = list_ID
        self._current_function_ack = False
        self._current_function_response = False
        self._current_function_response_data = None
        self.send_message(msg)
        sleep(0.5)
        if self._current_function_response:
            return True
        else:
            return False

    def unlock_all_positions(self, list_ID):
        arb_id = self.create_arbitration_id(self._can_controller_id, list_ID, CAN_MSG_TYPE_SET,
                                            CAN_FUNCTION_ALL_KEYLOCKS)

        msg = can.Message(arbitration_id=arb_id,
                          data=[0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11],
                          is_extended_id=True)
        self._current_function = CAN_FUNCTION_ALL_KEYLOCKS
        self._current_function_list_id = list_ID
        self._current_function_ack = False
        self._current_function_response = False
        self._current_function_response_data = None
        self.send_message(msg)
        sleep(0.5)
        if self._current_function_response:
            return True
        else:
            return False

    def get_key_id(self, list_ID, key_position):

        # Decrementing pos/slot as KMS position ranges from 0 to 13
        key_position -= 1
        # print("\nInside get key id function")
        can_function = CAN_FUNCTION_KEY_ID | key_position
        # can_function = (CAN_FUNCTION_KEY_ID & key_position)
        # print("Can Function: " + str(can_function))
        arb_id = self.create_arbitration_id(self._can_controller_id, list_ID, CAN_MSG_TYPE_GET,
                                            can_function)
        # print("Arb Id: " + str(arb_id))
        msg = can.Message(arbitration_id=arb_id,
                          data=[],
                          is_extended_id=True)
        self._current_function = can_function
        self._current_function_list_id = list_ID
        self._currekey_listsnt_function_ack = False
        self._current_function_response = False
        self._current_function_response_data = None
        self.send_message(msg)
        sleep(0.5)
        if self._current_function_response:
            if self._current_function_response_data is not None:
                result_list = list(self._current_function_response_data)
                key_fob_id = ''
                for num in result_list[:5]:
                    key_fob_id += str(num)
                return int(key_fob_id)
        else:
            return False


    def send_message(self, message):

        try:
            self.bus.send(message)
            return True
        except can.CanError:
            print("message not sent!")
            return False

    def flush_buffer(self):

        msg = self.buffer.get_message()
        while msg is not None:
            msg = self.buffer.get_message()

    def cleanup(self):

        self.notifier.stop()
        self.bus.shutdown()

    # @property
    # def lib_door_lock(self):
    #     return self._lib_door_lock

    # @lib_door_lock.setter
    # def lib_door_lock(self, value):
    #     self._lib_door_lock = value


def main():

    ams_can = AMS_CAN()
    sleep(6)
    print("Getting version no from list 1 & 2")
    strip_version = ams_can.get_version_number(1)
    if strip_version:
        print("Keystrip 1 version:" + str(strip_version))
    # sleep(2)
    strip_version = ams_can.get_version_number(2)
    if strip_version:
        print("Keystrip 2 version:" + str(strip_version))
    # ams_can = AMS_CAN()
    # sleep(3)

    ams_can.set_all_LED_ON(1, False)
    ams_can.set_all_LED_ON(2, False)
    sleep(4)
    ams_can.set_all_LED_OFF(1)
    ams_can.set_all_LED_OFF(2)
    # sleep(5)
    # ams_can = AMS_CAN()
    # sleep(3)
    print("No of keylists = " + str(len(ams_can.key_lists)))

    for keys in ams_can.key_lists:
        print("Key-list Id : " + str(keys))

    print("Setting all list to lock and LED-OFF")
    for list_id in ams_can.key_lists:
        ams_can.lock_all_positions(list_id)
        sleep(1)
        ams_can.set_all_LED_OFF(list_id)
        sleep(1)

    for list_id in ams_can.key_lists:
        print("Setting STRIP-" + str(list_id) + " LED 1 to ON STATE: " + str(ams_can.set_single_LED_state(list_id, 1, CAN_LED_STATE_ON)))
        print("Setting STRIP-" + str(list_id) + " POSITION 1 to UN-LOCK state: " + str(
            ams_can.set_single_key_lock_state(list_id, 1, CAN_KEY_UNLOCKED)))
        sleep(1)
        print("Setting STRIP-" + str(list_id) + " LED 2 to ON STATE: " + str(
            ams_can.set_single_LED_state(list_id, 2, CAN_LED_STATE_ON)))
        print("Setting STRIP-" + str(list_id) + " POSITION 2 to UN-LOCK state: " + str(
            ams_can.set_single_key_lock_state(list_id, 2, CAN_KEY_UNLOCKED)))
        sleep(1)
        print("Setting STRIP-" + str(list_id) + " LED 3 to ON STATE: " + str(
            ams_can.set_single_LED_state(list_id, 3, CAN_LED_STATE_ON)))
        print("Setting STRIP-" + str(list_id) + " POSITION 3 to UN-LOCK state: " + str(
            ams_can.set_single_key_lock_state(list_id, 3, CAN_KEY_UNLOCKED)))
        sleep(1)
        print("Setting STRIP-" + str(list_id) + " LED 4 to ON STATE: " + str(
            ams_can.set_single_LED_state(list_id, 4, CAN_LED_STATE_ON)))
        print("Setting STRIP-" + str(list_id) + " POSITION 4 to UN-LOCK state: " + str(
            ams_can.set_single_key_lock_state(list_id, 4, CAN_KEY_UNLOCKED)))
        sleep(1)
        print("Setting STRIP-" + str(list_id) + " LED 5 to ON STATE: " + str(
            ams_can.set_single_LED_state(list_id, 5, CAN_LED_STATE_ON)))
        print("Setting STRIP-" + str(list_id) + " POSITION 5 to UN-LOCK state: " + str(
            ams_can.set_single_key_lock_state(list_id, 5, CAN_KEY_UNLOCKED)))
    sleep(1)

    print("Setting all list to lock and LED-OFF")
    for list_id in ams_can.key_lists:
        ams_can.lock_all_positions(list_id)
        ams_can.set_all_LED_OFF(list_id)
    #
    # print("Setting all LED to OFF STATE: " + str(ams_can.set_all_LED_OFF(1)))
    # sleep(3)
    # print("Locking ALL positions: " + str(ams_can.lock_all_positions(1)))
    # sleep(3)
    # print("Setting LED 1 to ON STATE: " + str(ams_can.set_single_LED_state(1, 1, CAN_LED_STATE_ON)))
    # sleep(3)
    # print("Setting POSITION 1 to UN-LOCK state: " + str(ams_can.set_single_key_lock_state(1,1, CAN_KEY_UNLOCKED)))
    # sleep(3)
    # print("Setting LED 2 to ON STATE: " + str(ams_can.set_single_LED_state(1, 2, CAN_LED_STATE_ON)))
    # sleep(3)
    # print("Setting POSITION 2 to UN-LOCK state: " + str(ams_can.set_single_key_lock_state(1, 2, CAN_KEY_UNLOCKED)))
    # sleep(3)
    # print("Setting LED 3 to BLINK STATE: " + str(ams_can.set_single_LED_state(1, 3, CAN_LED_STATE_BLINK)))
    # sleep(3)
    # print("Setting POSITION 3 to UN-LOCK state: " + str(ams_can.set_single_key_lock_state(1, 3, CAN_KEY_UNLOCKED)))
    # sleep(3)
    # print("Setting LED 1, 2,3 to OFF STATE: " + str(ams_can.set_single_LED_state(1, 1, CAN_LED_STATE_OFF)))
    # ams_can.set_single_LED_state(1, 2, CAN_LED_STATE_OFF)
    # ams_can.set_single_LED_state(1, 3, CAN_LED_STATE_OFF)
    # print("Locking ALL positions: " + str(ams_can.lock_all_positions(1)))
    # sleep(3)
    #
    # print("Locking ALL positions: " + str(ams_can.unlock_all_positions(1)))
    # sleep(3)
    # counter = 0
    # while counter < 30:
    #     sleep(1)
    #     counter += 1

    ams_can.cleanup()
    # print("Can Bus shutdown...signing off")

    return


if __name__ == '__main__':
    main()