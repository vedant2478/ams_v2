import json
import time
from datetime import datetime
from test import AMS_CAN   # <-- adjust import if filename differs

PEG_JSON_FILE = "peg_ids.json"
PEG_TXT_FILE = "peg_ids.txt"


def load_existing_peg_ids():
    try:
        with open(PEG_JSON_FILE, "r") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_peg_ids(peg_ids):
    peg_list = sorted(list(peg_ids))

    with open(PEG_JSON_FILE, "w") as f:
        json.dump(peg_list, f, indent=4)

    with open(PEG_TXT_FILE, "w") as f:
        for pid in peg_list:
            f.write(str(pid) + "\n")


def main():
    print("🚀 Starting PEG ID collector")
    print("📡 Waiting for key insert / key take events...\n")

    ams_can = AMS_CAN()
    collected_peg_ids = load_existing_peg_ids()

    print(f"📦 Loaded {len(collected_peg_ids)} existing peg IDs")

    try:
        while True:
            # ---------------- KEY INSERTED ----------------
            if ams_can.key_inserted_event:
                peg_id = ams_can.key_inserted_id
                slot = ams_can.key_inserted_position_slot
                strip = ams_can.key_inserted_position_list

                print(
                    f"[INSERTED] PEG ID={peg_id} | strip={strip} | slot={slot}"
                )

                if peg_id not in collected_peg_ids:
                    collected_peg_ids.add(peg_id)
                    save_peg_ids(collected_peg_ids)
                    print("✅ New peg ID saved")

                ams_can.key_inserted_event = False

            # ---------------- KEY TAKEN ----------------
            if ams_can.key_taken_event:
                peg_id = ams_can.key_taken_id
                slot = ams_can.key_taken_position_slot
                strip = ams_can.key_taken_position_list

                print(
                    f"[TAKEN] PEG ID={peg_id} | strip={strip} | slot={slot}"
                )

                if peg_id not in collected_peg_ids:
                    collected_peg_ids.add(peg_id)
                    save_peg_ids(collected_peg_ids)
                    print("✅ New peg ID saved")

                ams_can.key_taken_event = False

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n🛑 Stopping PEG ID collector")

    finally:
        ams_can.cleanup()
        print("🧹 CAN cleaned up")
        print(f"📁 Final peg IDs stored in {PEG_JSON_FILE} & {PEG_TXT_FILE}")


if __name__ == "__main__":
    main()
