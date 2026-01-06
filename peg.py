# test_peg_registration.py

from datetime import datetime
from time import sleep

# ================= DB SETUP =================
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from csi_ams.utils.commons import (
    SQLALCHEMY_DATABASE_URI,
    TZ_INDIA,
    AUTH_MODE_PIN,
    EVENT_DOOR_OPEN,
    EVENT_DOOR_CLOSED,
    EVENT_PEG_REGISTERATION,
    EVENT_TYPE_EVENT,
)

from csi_ams.model import (
    AMS_Keys,
    AMS_Key_Pegs,
    AMS_Access_Log,
    AMS_Event_Log,
)

from csi_ams.utils.commons import get_event_description

# ================= CAN =================
from test import AMS_CAN   # adjust import if needed

# ================= INIT =================
engine = create_engine(SQLALCHEMY_DATABASE_URI)
Session = sessionmaker(bind=engine)
session = Session()

ams_can = AMS_CAN()

# ================= MOCK USER =================
USER_ID = 1  # change if required

# =====================================================
# PEG REGISTRATION TEST
# =====================================================

def run_peg_registration_test():
    print("\n========== PEG REGISTRATION TEST START ==========\n")

    # -------------------------------------------------
    # ACCESS LOG (Door Open)
    # -------------------------------------------------
    access_log = AMS_Access_Log(
        signInTime=datetime.now(TZ_INDIA),
        signInMode=AUTH_MODE_PIN,
        signInFailed=0,
        signInSucceed=1,
        signInUserId=USER_ID,
        activityCodeEntryTime=None,
        activityCode=1,
        doorOpenTime=datetime.now(TZ_INDIA),
        keysAllowed=None,
        keysTaken=None,
        keysReturned=None,
        doorCloseTime=None,
        event_type_id=EVENT_DOOR_OPEN,
        is_posted=0,
    )
    session.add(access_log)
    session.commit()

    print(f"[INFO] Door Open Logged | access_log_id={access_log.id}")

    # -------------------------------------------------
    # EVENT: DOOR OPEN
    # -------------------------------------------------
    event_desc = get_event_description(session, EVENT_DOOR_OPEN)

    session.add(
        AMS_Event_Log(
            userId=USER_ID,
            keyId=None,
            activityId=1,
            eventId=EVENT_DOOR_OPEN,
            loginType="PIN",
            access_log_id=access_log.id,
            timeStamp=datetime.now(TZ_INDIA),
            event_type=EVENT_TYPE_EVENT,
            eventDesc=event_desc,
            is_posted=0,
        )
    )
    session.commit()

    # -------------------------------------------------
    # CLEAR OLD PEG DATA
    # -------------------------------------------------
    session.query(AMS_Key_Pegs).delete()
    session.commit()
    print("[INFO] Old peg records cleared")

    # -------------------------------------------------
    # PEG SCAN LOOP
    # -------------------------------------------------
    for keylistid in ams_can.key_lists:
        print(f"\n--- Scanning Key Strip {keylistid} ---")

        for slot in range(1, 15):
            peg_id = ams_can.get_key_id(keylistid, slot)

            if not peg_id:
                print(f"[EMPTY] Strip {keylistid} Slot {slot}")
                continue

            key_pos_no = slot + ((keylistid - 1) * 14)

            print(
                f"[FOUND] Peg ID {peg_id} | Strip {keylistid} Slot {slot} | Key {key_pos_no}"
            )

            # Insert peg table
            new_peg = AMS_Key_Pegs(
                peg_id=peg_id,
                keylist_no=keylistid,
                keyslot_no=slot,
            )
            session.add(new_peg)
            session.commit()

            # Update key table
            key = (
                session.query(AMS_Keys)
                .filter(
                    (AMS_Keys.keyStrip == keylistid)
                    & (AMS_Keys.keyPosition == slot)
                )
                .first()
            )

            if key:
                key.peg_id = peg_id
                key.current_pos_strip_id = keylistid
                key.current_pos_slot_no = slot
                session.commit()
                print(f"[DB] AMS_Keys updated for Key {key_pos_no}")
            else:
                print(f"[WARN] AMS_Keys entry missing for strip {keylistid} slot {slot}")

            sleep(0.2)

    # -------------------------------------------------
    # EVENT: PEG REGISTRATION
    # -------------------------------------------------
    event_desc = get_event_description(session, EVENT_PEG_REGISTERATION)

    session.add(
        AMS_Event_Log(
            userId=USER_ID,
            keyId=None,
            activityId=1,
            eventId=EVENT_PEG_REGISTERATION,
            loginType="PIN",
            access_log_id=access_log.id,
            timeStamp=datetime.now(TZ_INDIA),
            event_type=EVENT_PEG_REGISTERATION,
            eventDesc=event_desc,
            is_posted=0,
        )
    )
    session.commit()

    # -------------------------------------------------
    # EVENT: DOOR CLOSED
    # -------------------------------------------------
    event_desc = get_event_description(session, EVENT_DOOR_CLOSED)

    session.add(
        AMS_Event_Log(
            userId=USER_ID,
            keyId=None,
            activityId=1,
            eventId=EVENT_DOOR_CLOSED,
            loginType="PIN",
            access_log_id=access_log.id,
            timeStamp=datetime.now(TZ_INDIA),
            event_type=EVENT_TYPE_EVENT,
            eventDesc=event_desc,
            is_posted=0,
        )
    )

    access_log.doorCloseTime = datetime.now(TZ_INDIA)
    session.commit()

    print("\n========== PEG REGISTRATION TEST COMPLETED ==========\n")


# =====================================================
if __name__ == "__main__":
    run_peg_registration_test()
