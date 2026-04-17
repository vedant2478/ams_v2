# hardware_sync.py

def sync_hardware_to_db(session, ams_can):
    """
    Sync hardware status to database using existing AMS_CAN instance.

    Args:
        session: SQLAlchemy session
        ams_can: Existing AMS_CAN instance (already initialized)

    Status convention:
        keyStatus = 0 → IN (present in slot)
        keyStatus = 1 → OUT (taken/empty)

    Note: Hardware-to-DB sync is disabled per dev request.
    We still detect strips so key_lists is populated.
    """
    print("=" * 60)
    print("AUTO SYNC: Hardware → Database [DISABLED PER DEV REQUEST]")
    print("=" * 60)

    if not ams_can:
        print("[SYNC] No CAN instance available.")
        return False

    # Detect strips if none found yet (scan 1–4 only; each strip already
    # has a 0.2 s sleep inside get_version_number so no extra delay needed)
    if not ams_can.key_lists:
        print("[SYNC] Detecting key strips (1–4)...")
        for strip_id in range(1, 5):
            version = ams_can.get_version_number(strip_id)
            if version:
                if strip_id not in ams_can.key_lists:
                    ams_can.key_lists.append(strip_id)
                print(f"  ✓ Strip {strip_id} detected (v{version})")
            else:
                print(f"  ✗ Strip {strip_id} not found")
    else:
        print(f"[SYNC] Strips already detected: {ams_can.key_lists}")

    if not ams_can.key_lists:
        print("[SYNC] No strips found — using fallback strip 1.")
        ams_can.key_lists = [1]

    print(f"[SYNC] Active strips: {ams_can.key_lists}")

    # DB sync intentionally skipped — current keyStatus values preserved.
    return True
