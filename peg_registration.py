from time import sleep
import paho.mqtt.client as mqtt
from kivy.clock import Clock

from csi_ams.model import AMS_Keys, AMS_Key_Pegs
from amscan import CAN_LED_STATE_BLINK, CAN_LED_STATE_OFF


class PegRegistrationService:
    """
    Peg registration using the SAME flow as old LCD code.
    No discovery. No re-init. Uses existing ams_can.
    """

    def __init__(self, manager):
        self.manager = manager
        self.session = manager.db_session
        self.user_auth = manager.user_auth
        self.ams_can = manager.ams_can  # 🔑 reuse existing CAN instance

        self._mqtt_client = None
        self._door_open = False
        self._scan_started = False

    # --------------------------------------------------
    # ENTRY POINT (ADMIN BUTTON)
    # --------------------------------------------------
    def start(self):
        print("\n========== [PEG] REGISTRATION START ==========")

        if self.user_auth["roleId"] != 1:
            print("[PEG][ERROR] Non-admin blocked")
            return False

        # EXACT SAME CHECK AS OLD CODE
        print(f"[PEG] Keylists available: {self.ams_can.key_lists}")

        if not self.ams_can.key_lists:
            print("[PEG][ERROR] No keylists present (CAN not initialized earlier)")
            return False

        # Unlock all pegs
        for keylistid in self.ams_can.key_lists:
            print(f"[PEG] Unlocking strip {keylistid}")
            self.ams_can.unlock_all_positions(keylistid)
            self.ams_can.set_all_LED_ON(keylistid, False)

        # Same DB check as old code
        missing = (
            self.session.query(AMS_Keys)
            .filter(AMS_Keys.keyStatus == 0)
            .count()
        )

        if missing > 0:
            print(f"[PEG][ABORT] {missing} keys missing. Insert all keys first.")
            self._cleanup()
            return False

        print("[PEG] Waiting for door OPEN")
        self._start_gpio_subscriber()
        return True

    # --------------------------------------------------
    # MQTT DOOR HANDLING (REPLACES GPIO LOOP)
    # --------------------------------------------------
    def _start_gpio_subscriber(self):
        self._mqtt_client = mqtt.Client("peg-reg-subscriber")
        self._mqtt_client.on_connect = lambda c, u, f, r: c.subscribe("gpio/pin32")
        self._mqtt_client.on_message = self._on_mqtt_message
        self._mqtt_client.connect("localhost", 1883, 60)
        self._mqtt_client.loop_start()

    def _on_mqtt_message(self, client, userdata, msg):
        value = int(msg.payload.decode())
        print(f"[PEG][MQTT] gpio/pin32 = {value}")

        if value == 1 and not self._door_open:
            self._door_open = True
            print("[PEG] Door OPENED")

        elif value == 0 and self._door_open:
            print("[PEG] Door CLOSED → scanning")
            self._scan_started = True
            self._scan_pegs()
            self._cleanup()

    # --------------------------------------------------
    # SCAN (DIRECT TRANSLATION OF OLD CODE)
    # --------------------------------------------------
    def _scan_pegs(self):
        print("[PEG] Scan in progress")

        scanned = []

        for keylistid in self.ams_can.key_lists:
            for slot in range(1, 15):

                self.ams_can.set_single_LED_state(
                    keylistid, slot, CAN_LED_STATE_BLINK
                )
                sleep(0.15)

                peg_id = self.ams_can.get_key_id(keylistid, slot)
                print(f"[PEG] strip={keylistid} slot={slot} peg_id={peg_id}")

                if peg_id:
                    scanned.append((peg_id, keylistid, slot))

                self.ams_can.set_single_LED_state(
                    keylistid, slot, CAN_LED_STATE_OFF
                )

        if not scanned:
            print("[PEG][ERROR] No pegs detected. DB untouched.")
            return

        print(f"[PEG] {len(scanned)} pegs detected. Updating DB.")

        # EXACT OLD BEHAVIOR: delete then insert
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
        print("[PEG] Peg registration DONE")

    # --------------------------------------------------
    # CLEANUP (SAME AS OLD)
    # --------------------------------------------------
    def _cleanup(self):
        print("[PEG] Cleaning up")

        for keylistid in self.ams_can.key_lists:
            self.ams_can.lock_all_positions(keylistid)
            self.ams_can.set_all_LED_OFF(keylistid)

        if self._mqtt_client:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()

        print("========== [PEG] REGISTRATION FINISHED ==========\n")
