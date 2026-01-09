# test_sync_hardware.py

from datetime import datetime
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# import your existing engine / Session / models / AMS_CAN
from model import AMS_Keys  # adjust import if needed
from db import engine                # or wherever your engine is
from amscan import AMS_CAN
from csi_ams.utils.commons import SLOT_STATUS_KEY_NOT_PRESENT, SQLALCHEMY_DATABASE_URI

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("TEST_SYNC")

engine = create_engine(
            SQLALCHEMY_DATABASE_URI,
            connect_args={"check_same_thread": False},
        )

SessionLocal = sessionmaker(bind=engine)


def sync_hardware_state_to_db(session, ams_can):
    """
    Standalone version: just CAN → DB sync, no UI, no Kivy.
    """
    if not ams_can:
        log.warning("[SYNC] AMS_CAN not initialised, skipping hardware sync")
        return

    log.info("[SYNC] Starting hardware → DB sync (standalone tester)")

    # Reset only keyStatus; keep mapping so we know which key belongs to which slot.
    updated = session.query(AMS_Keys).update(
        {"keyStatus": SLOT_STATUS_KEY_NOT_PRESENT}
    )
    log.info(f"[SYNC] Reset {updated} keys in DB to OUT (status only)")

    if not ams_can.key_lists:
        log.warning("[SYNC] ams_can.key_lists is empty; no strips detected")
    else:
        log.info(f"[SYNC] Scanning strips: {ams_can.key_lists}")

    present_count = 0

    # Helper: (strip,pos) -> AMS_Keys row; dynamic + static mapping
    def get_key_for_slot(strip_id, pos):
        # 1) dynamic mapping if already set
        row = session.query(AMS_Keys).filter(
            AMS_Keys.current_pos_strip_id == strip_id,
            AMS_Keys.current_pos_slot_no == pos,
        ).first()
        if row:
            return row

        # 2) fallback: static cabinet layout (door/strip/position)
        return session.query(AMS_Keys).filter(
            AMS_Keys.strip == strip_id,
            AMS_Keys.position == pos,
        ).first()

    for strip_id in ams_can.key_lists:
        for pos in range(1, 15):   # slots 1..14
            key_fob_id = ams_can.get_key_id(strip_id, pos)
            log.debug(f"[SYNC] strip={strip_id} pos={pos} get_key_id={key_fob_id}")

            if key_fob_id is False or key_fob_id is None:
                continue

            key_fob_str = str(key_fob_id)

            # -------- CASE 1: NO KEY PRESENT (all zeros) --------
            if key_fob_str.strip("0") == "":
                key_row = get_key_for_slot(strip_id, pos)
                if key_row:
                    key_row.keyStatus = SLOT_STATUS_KEY_NOT_PRESENT
                    log.info(
                        f"[SYNC] Slot empty, marked OUT: peg_id={key_row.peg_id} "
                        f"name={getattr(key_row, 'keyName', None)} "
                        f"strip={strip_id} pos={pos}"
                    )
                else:
                    log.info(
                        f"[SYNC] Slot empty, no peg mapped in DB "
                        f"(strip={strip_id}, pos={pos})"
                    )
                continue

            # -------- CASE 2: REAL KEY PRESENT --------
            try:
                peg_int = int(key_fob_str)
            except ValueError:
                log.warning(
                    f"[SYNC] Non-numeric key_fob_id '{key_fob_str}' at "
                    f"strip={strip_id} pos={pos}"
                )
                continue

            key_row = session.query(AMS_Keys).filter(
                AMS_Keys.peg_id == peg_int
            ).first()

            if not key_row:
                log.warning(
                    f"[SYNC] Peg not found in DB for peg_id={peg_int} "
                    f"(strip={strip_id}, pos={pos})"
                )
                continue

            key_row.keyStatus = 0  # IN
            key_row.current_pos_strip_id = strip_id
            key_row.current_pos_slot_no = pos
            present_count += 1
            log.info(
                f"[SYNC] Marked IN: peg_id={peg_int}, "
                f"name={getattr(key_row, 'keyName', None)} strip={strip_id} pos={pos}"
            )

    session.commit()
    log.info(f"[SYNC] Hardware sync complete. Marked {present_count} keys as IN")

    # Print final state for all keys for debugging
    all_keys = session.query(AMS_Keys).order_by(AMS_Keys.id).all()
    log.info("==== FINAL KEY STATES ====")
    for k in all_keys:
        log.info(
            f"id={k.id}, name={getattr(k, 'keyName', None)}, "
            f"peg={k.peg_id}, status={k.keyStatus}, "
            f"strip={k.current_pos_strip_id}, pos={k.current_pos_slot_no}"
        )


def main():
    log.info("=== TEST: CAN → DB sync ===")
    session = SessionLocal()

    # Init CAN
    ams_can = AMS_CAN()
    ams_can.get_version_number(1)
    ams_can.get_version_number(2)

    # Run sync once
    sync_hardware_state_to_db(session, ams_can)

    # Clean up CAN
    ams_can.cleanup()
    log.info("=== DONE ===")


if __name__ == "__main__":
    main()
