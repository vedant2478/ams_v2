from time import sleep
import paho.mqtt.client as mqtt
from kivy.clock import Clock

from amscan import AMS_CAN, CAN_LED_STATE_BLINK, CAN_LED_STATE_OFF
from csi_ams.model import AMS_Keys, AMS_Key_Pegs


class PegRegistrationService:
    """
    Peg Registration Service
    - Callable from AdminScreen
    - MQTT lifecycle inside
    - SAFE DB handling
    """

    def __init__(self, manager):
        self.manager = manager
        self.session = manager.db_session
        self.user_auth = manager.user_auth

        self._mqtt_client = None
        self._door_open = False
        self._scan_started = False
        self._active = False

    # =====================================================
    # ENTRY POINT
    # =====================================================
    def start(self):
        print("\n========== [PEG] REGISTRATION START ==========")

        if self.user_auth["roleId"] != 1:
            print("[PEG][ERROR] Non-admin access blocked")
            return False

        self._active = True
        self._door_open = False
        self._scan_started = False

        # -------- ENSURE CAN --------
        if not hasattr(self.manager, "ams_can"):
            self.manager.ams_can = AMS_CAN()

        ams_can = self.manager.ams_can

        # -------- ENSURE key_lists POPULATED --------
        if not ams_can.key_lists:
            print("[PEG][FIX] key_lists empty → forcing discovery")
            try:
                ams_can.discover_key_lists()
            except Exception as e:
                print("[PEG][ERROR] key list discovery failed:", e)
                self._cleanup()
                return False

        print(f"[PEG] key_lists detected: {ams_can.key_lists}")

        # -------- UNLOCK PEGS --------
        print("[PEG] Unlocking all peg positions")
        for strip in ams_can.key_lists:
            ams_can.unlock_all_positions(strip)
            ams_can.set_all_LED_ON(strip, False)

        # -------- START MQTT --------
        self._start_gpio_subscriber()
        print("[PEG] Waiting for door OPEN")

        return True

    # =====================================================
    # MQTT
    # =====================================================
    def _start_gpio_subscriber(self):
        print("[PEG][MQTT] Starting GPIO subscriber")

        self._mqtt_client = mqtt.Client("peg-reg-subscriber")
        self._mqtt_client.on_connect = self._on_mqtt_connect
        self._mqtt_client.on_message = self._on_mqtt_message
        self._mqtt_client.connect("localhost", 1883, 60)
        self._mqtt_client.loop_start()

    def _stop_gpio_subscriber(self):
        if self._mqtt_client:
            print("[PEG][MQTT] Stopping GPIO subscriber")
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()
            self._mqtt_client = None

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        print("[PEG][MQTT] Connected (rc =", rc, ")")
        client.subscribe("gpio/pin32")

    def _on_mqtt_message(self, client, userdata, msg):
        if not self._active:
            return

        value = int(msg.payload.decode())
        print(f"[PEG][MQTT] gpio/pin32 = {value}")

        if value == 1 and not self._door_open:
            Clock.schedule_once(lambda dt: self._on_door_opened())

        elif value == 0 and self._door_open:
            Clock.schedule_once(lambda dt: self._on_door_closed())

    # =====================================================
    # DOOR EVENTS
    # =====================================================
    def _on_door_opened(self):
        print("[PEG] Door OPENED")
        self._door_open = True

    def _on_door_closed(self):
        if not self._door_open or self._scan_started:
            return

        print("[PEG] Door CLOSED → start scanning")
        self._scan_started = True
        self._scan_pegs()
        self._cleanup()

    # =====================================================
    # SAFE PEG SCAN (FIXED)
    # =====================================================
    def _scan_pegs(self):
        session = self.session
        ams_can = self.manager.ams_can

        print("[PEG] ===== STARTING PEG SCAN =====")

        scanned = []
        total_reads = 0

        for strip in ams_can.key_lists:
            print(f"[PEG] Scanning strip {strip}")

            for slot in range(1, 15):
                total_reads += 1

                ams_can.set_single_LED_state(strip, slot, CAN_LED_STATE_BLINK)
                sleep(0.12)  # 🔴 CRITICAL CAN SETTLE TIME

                peg_id = ams_can.get_key_id(strip, slot)
                print(
                    f"[PEG][SCAN] strip={strip} slot={slot} peg_id={peg_id}"
                )

                if peg_id:
                    scanned.append((peg_id, strip, slot))

                ams_can.set_single_LED_state(strip, slot, CAN_LED_STATE_OFF)

        print(f"[PEG] Total CAN reads: {total_reads}")
        print(f"[PEG] Pegs detected: {len(scanned)}")

        if not scanned:
            print("[PEG][ERROR] NO PEGS DETECTED — DB NOT TOUCHED")
            return

        # -------- SAFE DB UPDATE --------
        print("[PEG] Updating DB with new peg mappings")

        session.query(AMS_Key_Pegs).delete()
        session.commit()
        print("[PEG] Old peg mappings cleared")

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
        print("[PEG] ===== PEG REGISTRATION SUCCESS =====")

    # =====================================================
    # CLEANUP
    # =====================================================
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
