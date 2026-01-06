from time import sleep, time
import paho.mqtt.client as mqtt
from kivy.clock import Clock

from csi_ams.model import AMS_Keys, AMS_Key_Pegs
from amscan import AMS_CAN
from amscan import CAN_LED_STATE_BLINK, CAN_LED_STATE_OFF


class PegRegistrationService:

    INIT_TIMEOUT = 8        # seconds to wait for keylist discovery
    KEY_READ_RETRIES = 3    # retries per slot

    def __init__(self, manager):
        self.manager = manager
        self.session = manager.db_session
        self.user_auth = manager.user_auth

        self._mqtt_client = None
        self._door_open = False
        self._scan_started = False
        self._active = False

    # -------------------------------------------------
    # ENTRY POINT
    # -------------------------------------------------
    def start(self):
        print("\n========== [PEG] REGISTRATION START ==========")

        if self.user_auth["roleId"] != 1:
            print("[PEG][ERROR] Non-admin blocked")
            return False

        self._active = True

        # -------- ENSURE CAN --------
        if not hasattr(self.manager, "ams_can"):
            self.manager.ams_can = AMS_CAN()

        ams_can = self.manager.ams_can

        # -------- WAIT FOR INIT / KEYLISTS --------
        print("[PEG] Waiting for keylist discovery...")
        start = time()

        while not ams_can.key_lists and (time() - start) < self.INIT_TIMEOUT:
            sleep(0.2)

        if not ams_can.key_lists:
            print("[PEG][ERROR] No keylists discovered after timeout")
            self._cleanup()
            return False

        print(f"[PEG] Keylists discovered: {ams_can.key_lists}")

        # -------- UNLOCK PEGS --------
        for strip in ams_can.key_lists:
            ams_can.unlock_all_positions(strip)
            ams_can.set_all_LED_ON(strip, False)

        # -------- START MQTT --------
        self._start_gpio_subscriber()
        print("[PEG] Waiting for door OPEN")

        return True

    # -------------------------------------------------
    # MQTT
    # -------------------------------------------------
    def _start_gpio_subscriber(self):
        self._mqtt_client = mqtt.Client("peg-reg-subscriber")
        self._mqtt_client.on_connect = lambda c, u, f, r: c.subscribe("gpio/pin32")
        self._mqtt_client.on_message = self._on_mqtt_message
        self._mqtt_client.connect("localhost", 1883, 60)
        self._mqtt_client.loop_start()

    def _stop_gpio_subscriber(self):
        if self._mqtt_client:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()

    def _on_mqtt_message(self, client, userdata, msg):
        value = int(msg.payload.decode())
        print(f"[PEG][MQTT] gpio/pin32 = {value}")

        if value == 1 and not self._door_open:
            Clock.schedule_once(lambda dt: self._on_door_opened())

        elif value == 0 and self._door_open:
            Clock.schedule_once(lambda dt: self._on_door_closed())

    # -------------------------------------------------
    # DOOR EVENTS
    # -------------------------------------------------
    def _on_door_opened(self):
        print("[PEG] Door OPENED")
        self._door_open = True

    def _on_door_closed(self):
        if self._scan_started:
            return

        print("[PEG] Door CLOSED → scanning")
        self._scan_started = True
        self._scan_pegs()
        self._cleanup()

    # -------------------------------------------------
    # PEG SCAN (CAN-CORRECT)
    # -------------------------------------------------
    def _scan_pegs(self):
        ams_can = self.manager.ams_can
        session = self.session

        scanned = []

        for strip in ams_can.key_lists:
            print(f"[PEG] Scanning strip {strip}")

            for slot in range(1, 15):
                ams_can.set_single_LED_state(strip, slot, CAN_LED_STATE_BLINK)
                sleep(0.15)

                peg_id = False
                for attempt in range(self.KEY_READ_RETRIES):
                    peg_id = ams_can.get_key_id(strip, slot)
                    print(
                        f"[PEG][SCAN] strip={strip} slot={slot} "
                        f"attempt={attempt+1} peg_id={peg_id}"
                    )
                    if peg_id:
                        break
                    sleep(0.1)

                ams_can.set_single_LED_state(strip, slot, CAN_LED_STATE_OFF)

                if peg_id:
                    scanned.append((peg_id, strip, slot))

        if not scanned:
            print("[PEG][ERROR] No pegs detected → DB untouched")
            return

        print(f"[PEG] Pegs detected: {len(scanned)}")

        # -------- SAFE DB UPDATE --------
        session.query(AMS_Key_Pegs).delete()
        session.commit()

        for peg_id, strip, slot in scanned:
            session.add(
                AMS_Key_Pegs(
                    peg_id=peg_id,
                    keylist_no=strip,
                    keyslot_no=slot,
                )
            )

            key = session.query(AMS_Keys).filter(
                AMS_Keys.keyStrip == strip,
                AMS_Keys.keyPosition == slot,
            ).first()

            if key:
                key.peg_id = peg_id
                key.current_pos_strip_id = strip
                key.current_pos_slot_no = slot

        session.commit()
        print("[PEG] Peg registration SUCCESS")

    # -------------------------------------------------
    # CLEANUP
    # -------------------------------------------------
    def _cleanup(self):
        print("[PEG] Cleaning up")

        ams_can = self.manager.ams_can
        for strip in ams_can.key_lists:
            ams_can.lock_all_positions(strip)
            ams_can.set_all_LED_OFF(strip)

        self._stop_gpio_subscriber()
        self._active = False
        self._door_open = False
        self._scan_started = False

        print("========== [PEG] REGISTRATION FINISHED ==========\n")
