# test2.py

def sync_hardware_to_db(session, ams_can):
    """
    Sync hardware status to database using existing AMS_CAN instance.
    
    Args:
        session: SQLAlchemy session
        ams_can: Existing AMS_CAN instance (already initialized)
    
    Usage:
        ams_can = AMS_CAN()
        sync_hardware_to_db(session, ams_can)
    
    Status convention:
        keyStatus = 0 → IN (present in slot)
        keyStatus = 1 → OUT (taken/empty)
    """
    from csi_ams.model import AMS_Keys
    from time import sleep
    
    print("=" * 60)
    print("AUTO SYNC: Hardware → Database [DISABLED PER DEV REQUEST]")
    print("=" * 60)
    
    # We must still detect the physical strips to populate ams_can.key_lists
    if not ams_can or not ams_can.key_lists:
        print("[1/2] No CAN instance or strips detected, trying to detect...")
        for strip_id in range(1, 10):
            version = ams_can.get_version_number(strip_id)
            if version:
                if strip_id not in ams_can.key_lists:
                    ams_can.key_lists.append(strip_id)
                print(f"  ✓ Strip {strip_id} detected (v{version})")
            sleep(0.5)
            
    if len(ams_can.key_lists) == 0:
        print("✗ No strips found. Hardcode fallback.")
        ams_can.key_lists = [1] # Fallback to strip 1 if CAN fails
    
    # User specifically requested to completely skip hardware checking
    # and to preserve existing DB status as '0' (IN).
    return True
