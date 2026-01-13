# peg_registration.py

from time import sleep
from datetime import datetime
import pytz
import paho.mqtt.client as mqtt
from threading import Event

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
from amscan import CAN_LED_STATE_BLINK, CAN_LED_STATE_OFF
from hardware_sync import sync_hardware_to_db

TZ_INDIA = pytz.timezone("Asia/Kolkata")


def register_pegs(session, ams_can, user_id):
    """
    Complete peg registration flow:
    1. Sync hardware to DB
    2. Check all keys present
    3. Wait for door open/close
    4. Scan all pegs
    5. Update database
    
    Args:
        session: SQLAlchemy session
        ams_can: Existing AMS_CAN instance (must be initialized)
        user_id: User performing registration
    
    Returns:
        dict with 'success', 'message', and optional 'pegs_registered'
    """
    
    print("\n" + "="*60)
    print("PEG REGISTRATION STARTED")
    print("="*60)
    
    # ========================================
    # STEP 1: SYNC HARDWARE TO DB
    # ========================================
    print("\n[1/5] Syncing hardware state to database...")
    
    if not sync_hardware_to_db(session, ams_can):
        return {
            'success': False,
            'message': 'Hardware sync failed - no strips detected'
        }
    
    # ========================================
    # STEP 2: CHECK ALL KEYS PRESENT
    # ========================================
    print("\n[2/5] Checking if all keys are present...")
    
    missing_keys = (
        session.query(AMS_Keys)
        .filter(
            AMS_Keys.deletedAt == None,
            AMS_Keys.keyStatus == 1  # 1 = OUT/missing
        )
        .count()
    )
    
    if missing_keys > 0:
        print(f"❌ {missing_keys} key(s) are missing")
        return {
            'success': False,
            'message': f'{missing_keys} keys are missing. Please return all keys before registration.'
        }
    
    print("✓ All keys present")
    
    # ========================================
    # STEP 3: UNLOCK ALL + LED ON
    # ========================================
    print("\n[3/5] Unlocking all positions and turning LEDs on...")
    
    for strip in ams_can.key_lists:
        ams_can.unlock_all_positions(strip)
        ams_can.set_all_LED_ON(strip, False)
    
    # Create access log
    access_log = AMS_Access_Log(
        signInTime=datetime.now(TZ_INDIA),
        signInMode=AUTH_MODE_PIN,
        signInFailed=0,
        signInSucceed=1,
        signInUserId=user_id,
        activityCode=1,
        doorOpenTime=datetime.now(TZ_INDIA),
        event_type_id=EVENT_DOOR_OPEN,
        is_posted=0,
    )
    session.add(access_log)
    session.commit()
    
    # ========================================
    # STEP 4: WAIT FOR DOOR CYCLE
    # ========================================
    print("\n[4/5] Waiting for door to open and close...")
    print("Please open the door, then close it to start scanning...")
    
    door_event = Event()
    door_opened = {'value': False}
    
    def on_connect(client, userdata, flags, rc):
        client.subscribe("gpio/pin32")
        print("✓ Connected to MQTT, monitoring door sensor")
    
    def on_message(client, userdata, msg):
        value = int(msg.payload.decode())
        
        if value == 1 and not door_opened['value']:
            door_opened['value'] = True
            print("✓ Door opened")
        
        elif value == 0 and door_opened['value']:
            print("✓ Door closed - starting peg scan")
            door_event.set()
    
    mqtt_client = mqtt.Client("peg-registration")
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect("localhost", 1883, 60)
    mqtt_client.loop_start()
    
    # Wait for door cycle (with timeout)
    if not door_event.wait(timeout=300):  # 5 minute timeout
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        
        # Cleanup
        for strip in ams_can.key_lists:
            ams_can.unlock_all_positions(strip)
            ams_can.set_all_LED_OFF(strip)
        
        return {
            'success': False,
            'message': 'Timeout waiting for door cycle'
        }
    
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    
    # ========================================
    # STEP 5: SCAN PEGS
    # ========================================
    print("\n[5/5] Scanning peg IDs...")
    
    scanned_pegs = []
    
    for strip in ams_can.key_lists:
        print(f"\n  Scanning strip {strip}...")
        
        for slot in range(1, 15):  # positions 1-14
            # Blink LED for current position
            ams_can.set_single_LED_state(strip, slot, CAN_LED_STATE_BLINK)
            sleep(0.15)
            
            # Read peg ID
            peg_id = ams_can.get_key_id(strip, slot)
            
            if peg_id and str(peg_id).strip("0") != "":
                try:
                    peg_int = int(str(peg_id))
                    scanned_pegs.append({
                        'peg_id': peg_int,
                        'strip': strip,
                        'slot': slot
                    })
                    print(f"    Slot {slot:2d}: Peg ID {peg_int}")
                except ValueError:
                    print(f"    Slot {slot:2d}: Invalid peg ID '{peg_id}'")
            
            # Turn LED off
            ams_can.set_single_LED_state(strip, slot, CAN_LED_STATE_OFF)
    
    if not scanned_pegs:
        # Cleanup
        for strip in ams_can.key_lists:
            ams_can.unlock_all_positions(strip)
            ams_can.set_all_LED_OFF(strip)
        
        return {
            'success': False,
            'message': 'No peg IDs detected during scan'
        }
    
    print(f"\n✓ Scanned {len(scanned_pegs)} peg(s)")
    
    # ========================================
    # STEP 6: UPDATE DATABASE
    # ========================================
    print("\n[6/6] Updating database...")
    
    # Clear existing peg mappings
    session.query(AMS_Key_Pegs).delete()
    session.commit()
    
    # Insert new mappings
    for peg_data in scanned_pegs:
        # Add to AMS_Key_Pegs
        session.add(
            AMS_Key_Pegs(
                peg_id=peg_data['peg_id'],
                keylist_no=peg_data['strip'],
                keyslot_no=peg_data['slot'],
            )
        )
        
        # Update AMS_Keys
        key = (
            session.query(AMS_Keys)
            .filter(
                AMS_Keys.keyStrip == peg_data['strip'],
                AMS_Keys.keyPosition == peg_data['slot'],
                AMS_Keys.deletedAt == None
            )
            .first()
        )
        
        if key:
            key.peg_id = peg_data['peg_id']
            key.current_pos_strip_id = peg_data['strip']
            key.current_pos_slot_no = peg_data['slot']
            key.keyStatus = 0  # Mark as IN
    
    session.commit()
    
    # Add event log
    session.add(
        AMS_Event_Log(
            userId=user_id,
            eventId=EVENT_PEG_REGISTERATION,
            loginType="FRONTEND",
            access_log_id=access_log.id,
            timeStamp=datetime.now(TZ_INDIA),
            event_type=EVENT_TYPE_EVENT,
            eventDesc=get_event_description(session, EVENT_PEG_REGISTERATION),
            is_posted=0,
        )
    )
    session.commit()
    
    # ========================================
    # CLEANUP
    # ========================================
    print("\nCleaning up...")
    for strip in ams_can.key_lists:
        ams_can.unlock_all_positions(strip)
        ams_can.set_all_LED_OFF(strip)
    
    print("\n" + "="*60)
    print(f"PEG REGISTRATION COMPLETE - {len(scanned_pegs)} pegs registered")
    print("="*60 + "\n")
    
    return {
        'success': True,
        'message': f'Successfully registered {len(scanned_pegs)} pegs',
        'pegs_registered': len(scanned_pegs),
        'pegs': scanned_pegs
    }
