from time import sleep
from datetime import datetime
import pytz

from csi_ams.model import AUTH_MODE_PIN, EVENT_PEG_REGISTERATION, EVENT_TYPE_EVENT
from db_core import SQLALCHEMY_DATABASE_URI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from csi_ams.utils.commons import *
from amscan import AMS_CAN
from model import EVENT_DOOR_OPEN, AMS_Keys, AMS_Key_Pegs, AMS_Access_Log, AMS_Event_Log
from csi_ams.utils.commons import get_event_description


TZ_INDIA = pytz.timezone("Asia/Kolkata")


def wait_for_keylists(ams_can, timeout=15):
    print("Waiting for CAN key-lists...")
    while timeout > 0:
        if ams_can.key_lists:
            return True
        sleep(1)
        timeout -= 1
    return False


def main():
    # ---------------- DB ----------------
    engine = create_engine(SQLALCHEMY_DATABASE_URI)
    Session = sessionmaker(bind=engine)
    session = Session()

    # ---------------- CAN ----------------
    ams_can = AMS_CAN()

    # Trigger handshake (same as prod)
    ams_can.get_version_number(1)
    ams_can.get_version_number(2)

    if not wait_for_keylists(ams_can):
        print("❌ No key-lists detected from CAN")
        return

    print(f"✅ Key-lists detected: {ams_can.key_lists}")

    # ---------------- ACCESS LOG ----------------
    access_log = AMS_Access_Log(
        signInTime=datetime.now(TZ_INDIA),
        signInMode=AUTH_MODE_PIN,
        signInFailed=0,
        signInSucceed=1,
        signInUserId=1,
        activityCode=1,
        doorOpenTime=datetime.now(TZ_INDIA),
        event_type_id=EVENT_DOOR_OPEN,
        is_posted=0,
    )
    session.add(access_log)
    session.commit()

    # ---------------- CLEAR OLD PEGS ----------------
    session.query(AMS_Key_Pegs).delete()
    session.commit()
    print("Old peg records cleared")

    # ---------------- PEG SCAN ----------------
    for keylistid in ams_can.key_lists:
        print(f"\nScanning Strip {keylistid}")

        for slot in range(1, 15):
            peg_id = ams_can.get_key_id(keylistid, slot)
            print(f"Strip {keylistid} Slot {slot} → peg_id = {peg_id}")

            if not peg_id:
                continue

            # Insert peg
            session.add(
                AMS_Key_Pegs(
                    peg_id=peg_id,
                    keylist_no=keylistid,
                    keyslot_no=slot,
                )
            )
            session.commit()

            # Update key table
            key = (
                session.query(AMS_Keys)
                .filter(
                    AMS_Keys.keyStrip == keylistid,
                    AMS_Keys.keyPosition == slot,
                )
                .first()
            )

            if key:
                key.peg_id = peg_id
                key.current_pos_strip_id = keylistid
                key.current_pos_slot_no = slot
                session.commit()
                print("  → DB updated")

            sleep(0.2)

    # ---------------- EVENT LOG ----------------
    session.add(
        AMS_Event_Log(
            userId=1,
            eventId=EVENT_PEG_REGISTERATION,
            loginType="CLI",
            access_log_id=access_log.id,
            timeStamp=datetime.now(TZ_INDIA),
            event_type=EVENT_TYPE_EVENT,
            eventDesc=get_event_description(session, EVENT_PEG_REGISTERATION),
            is_posted=0,
        )
    )
    session.commit()

    print("\n✅ PEG REGISTRATION TEST COMPLETED\n")


if __name__ == "__main__":
    main()
