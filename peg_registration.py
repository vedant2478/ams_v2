from time import sleep
from datetime import datetime
import pytz
import paho.mqtt.client as mqtt

from csi_ams.model import (
    AMS_Keys,
    AMS_Key_Pegs,
    AMS_Access_Log,
    AMS_Event_Log,
    AUTH_MODE_PIN,
    EVENT_PEG_REGISTERATION,
    EVENT_DOOR_OPEN,
    EVENT_TYPE_EVENT,
)

from csi_ams.utils.commons import get_event_description
from amscan import (
    AMS_CAN,
    CAN_LED_STATE_BLINK,
    CAN_LED_STATE_OFF,
)

TZ_INDIA = pytz.timezone("Asia/Kolkata")


class PegRegistrationService:
    """
    Peg registration service
    - Own CAN instance
    - Own MQTT instance
    - Explicit CAN discovery
    - Full cleanup after completion
    """

    def __init__(self, manager):
        self.manager = manager
        self.session = manager.db_session

        # 🔴 LOCAL CAN INSTANCE (NOT SHARED)
        self.ams_can = AMS_CAN()

        self._mqtt_client = None
        self._door_open = False
        self._scan_started = False
        self._access_log = None

    # --------------------------------------------------
    # WAIT FOR KEYLISTS (AFTER DISCOVERY)
    # --------------------------------------------------
    def _wait_for_keylists(self, timeout=10):
        print("[PEG] Waiting for CAN keylists...")
        while timeout > 0:
            if self.ams_can.key_lists:
                return True
            sleep(1)
            timeout -= 1
        return False

    # --------------------------------------------------
    # ENTRY POINT
    # --------------------------------------------------
    def start(self):
        print("\n========== [PEG] REGISTRATION START ==========")

        # 🔑 EXPLICIT CAN DISCOVERY (MANDATORY)
        print("[PEG] Triggering CAN discovery")
        self.ams_can.get_version_number(1)
        self.ams_can.get_version_number(2)
        sleep(2)

        if not self._wait_for_keylists():
            print("[PEG][ERROR] No keylists detected from CAN")
            self._cleanup()
            return False

        print(f"[PEG] Keylists detected: {self.ams_can.key_lists}")

        # 🔓 UNLOCK ALL KEYS + LED ON
        for strip in self.ams_can.key_lists:
            self.ams_can.unlock_all_positions(strip)
            self.ams_can.set_all_LED_ON(strip, False)

        # ---------------- ENSURE ALL KEYS PRESENT ----------------
        missing = (
            self.session.query(AMS_Keys)
            .filter(AMS_Keys.keyStatus == 0)
            .count()
        )

        if missing > 0:
            print(f"[PEG][ABORT] {missing} keys missing")
            self._cleanup()
            return False

        # ---------------- ACCESS LOG ----------------
        self._access_log = AMS_Access_Log(
            signInTime=datetime.now(TZ_INDIA),
            signInMode=AUTH_MODE_PIN,
            signInFailed=0,
            signInSucceed=1,
            signInUserId=self.manager.user_id,
            activityCode=1,
            doorOpenTime=datetime.now(TZ_INDIA),
            event_type_id=EVENT_DOOR_OPEN,
            is_posted=0,
        )
        self.session.add(self._access_log)
        self.session.commit()

        print("[PEG] Waiting for door open (MQTT)")
        self._start_gpio_subscriber()
        return True

    # --------------------------------------------------
    # MQTT DOOR HANDLING
    # --------------------------------------------------
    def _start_gpio_subscriber(self):
        self._mqtt_client = mqtt.Client("peg-reg-subscriber")
        self._mqtt_client.on_connect = lambda c, u, f, r: c.subscribe("gpio/pin32")
        self._mqtt_client.on_message = self._on_mqtt_message
        self._mqtt_client.connect("localhost", 1883, 60)
        self._mqtt_client.loop_start()

    def _on_mqtt_message(self, client, userdata, msg):
        value = int(msg.payload.decode())
        print(f"[PEG][MQTT] Door GPIO = {value}")

        if value == 1 and not self._door_open:
            self._door_open = True
            print("[PEG] Door OPENED")

        elif value == 0 and self._door_open and not self._scan_started:
            print("[PEG] Door CLOSED → start scan")
            self._scan_started = True
            self._scan_pegs()

            self._cleanup()

    # --------------------------------------------------
    # PEG SCAN
    # --------------------------------------------------
    def _scan_pegs(self):
        print("[PEG] Scan started")

        scanned = []

        for strip in self.ams_can.key_lists:
            for slot in range(1, 15):

                self.ams_can.set_single_LED_state(
                    strip, slot, CAN_LED_STATE_BLINK
                )
                sleep(0.15)

                peg_id = self.ams_can.get_key_id(strip, slot)
                print(f"[PEG] strip={strip} slot={slot} peg_id={peg_id}")

                if peg_id:
                    scanned.append((peg_id, strip, slot))

                self.ams_can.set_single_LED_state(
                    strip, slot, CAN_LED_STATE_OFF
                )

        if not scanned:
            print("[PEG][ERROR] No pegs detected")
            return

        print(f"[PEG] {len(scanned)} pegs detected")

        # ---------------- RESET PEG TABLE ----------------
        self.session.query(AMS_Key_Pegs).delete()
        self.session.commit()

        for peg_id, strip, slot in scanned:
            self.session.add(
                AMS_Key_Pegs(
                    peg_id=peg_id,
                    keylist_no=strip,
                    keyslot_no=slot,
                )
            )

            key = (
                self.session.query(AMS_Keys)
                .filter(
                    AMS_Keys.keyStrip == strip,
                    AMS_Keys.keyPosition == slot,
                )
                .first()
            )

            if key:
                key.peg_id = peg_id
                key.current_pos_strip_id = strip
                key.current_pos_slot_no = slot

        self.session.commit()

        # ---------------- EVENT LOG ----------------
        self.session.add(
            AMS_Event_Log(
                userId=self.manager.user_id,
                eventId=EVENT_PEG_REGISTERATION,
                loginType="FRONTEND",
                access_log_id=self._access_log.id,
                timeStamp=datetime.now(TZ_INDIA),
                event_type=EVENT_TYPE_EVENT,
                eventDesc=get_event_description(
                    self.session, EVENT_PEG_REGISTERATION
                ),
                is_posted=0,
            )
        )
        self.session.commit()

        print("[PEG] Peg registration COMPLETED")

    # --------------------------------------------------
    # CLEANUP (CRITICAL)
    # --------------------------------------------------
    def _cleanup(self):
        print("[PEG] Cleanup")

        # 🔓 UNLOCK ALL + LED OFF
        if self.ams_can and self.ams_can.key_lists:
            for strip in self.ams_can.key_lists:
                self.ams_can.unlock_all_positions(strip)
                self.ams_can.set_all_LED_OFF(strip)

        # 🧹 CAN CLEANUP
        if self.ams_can:
            self.ams_can.cleanup()
            self.ams_can = None

        # 🧹 MQTT CLEANUP
        if self._mqtt_client:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()
            self._mqtt_client = None

        print("========== [PEG] REGISTRATION FINISHED ==========\n")


