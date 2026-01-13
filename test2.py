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
    print("AUTO SYNC: Hardware → Database")
    print("=" * 60)
    
    # Check if CAN is initialized
    if not ams_can or not ams_can.key_lists:
        print("[1/2] No CAN instance or strips detected, trying to detect...")
        for strip_id in range(1, 5):
            version = ams_can.get_version_number(strip_id)
            if version:
                print(f"  ✓ Strip {strip_id} detected (v{version})")
            sleep(0.5)
    
    if len(ams_can.key_lists) == 0:
        print("✗ No strips found. Aborting.")
        return False
    
    print(f"[1/2] Using {len(ams_can.key_lists)} strip(s): {ams_can.key_lists}")
    
    # Get all key records from DB
    print("[2/2] Syncing hardware to database...")
    key_records = (
        session.query(AMS_Keys)
        .filter(AMS_Keys.deletedAt == None)
        .order_by(AMS_Keys.keyStrip, AMS_Keys.keyPosition)
        .all()
    )
    
    # Group by strip
    strips_in_db = {}
    for key in key_records:
        strip_id = key.keyStrip
        if strip_id not in strips_in_db:
            strips_in_db[strip_id] = []
        strips_in_db[strip_id].append(key)
    
    print(f"  Found records for {len(strips_in_db)} strip(s) in DB")
    
    # Sync each strip
    total_synced = 0
    total_present = 0
    total_empty = 0
    
    for strip_id in ams_can.key_lists:
        if strip_id not in strips_in_db:
            print(f"\n⚠️  Strip {strip_id} has no DB records, skipping...")
            continue
        
        print(f"\n  Strip {strip_id}: Checking {len(strips_in_db[strip_id])} positions...")
        
        for key_record in strips_in_db[strip_id]:
            position = key_record.keyPosition
            
            # Check hardware
            key_id = ams_can.get_key_id(strip_id, position)
            is_present = bool(key_id and key_id != "00000" and key_id != False)
            
            # Update DB
            old_status = key_record.keyStatus
            
            # Status convention: 0 = IN/PRESENT, 1 = OUT/EMPTY
            if is_present:
                new_status = 0  # IN
                total_present += 1
            else:
                new_status = 1  # OUT
                total_empty += 1
            
            key_record.keyStatus = new_status
            
            # Log changes
            if old_status != new_status:
                status_text = "IN" if is_present else "OUT"
                key_name = key_record.keyName or f"Key-{position}"
                print(f"    Pos {position:2d} ({key_name}): {old_status} → {new_status} ({status_text})")
            
            total_synced += 1
            sleep(0.2)
    
    # Commit all changes
    try:
        session.commit()
        print(f"\n✓ Database updated successfully")
    except Exception as e:
        session.rollback()
        print(f"\n✗ Database commit failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Summary
    print(f"\n{'='*60}")
    print("SYNC SUMMARY")
    print(f"{'='*60}")
    print(f"Strips checked: {len(ams_can.key_lists)}")
    print(f"Total positions synced: {total_synced}")
    print(f"Keys present (IN): {total_present}")
    print(f"Empty positions (OUT): {total_empty}")
    print(f"{'='*60}")
    
    return True
