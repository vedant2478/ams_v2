def sync_hardware_to_db(session):
    """
    Automatically detect all key strips, check all positions, 
    and sync status to database.
    Just call this with a session and it handles everything.
    
    Usage:
        from test_key_status import sync_hardware_to_db
        sync_hardware_to_db(session)
    """
    from csi_ams.model import AMS_Keys
    from amscan import AMS_CAN
    from time import sleep
    
    print("=" * 60)
    print("AUTO SYNC: Hardware → Database")
    print("=" * 60)
    
    # Initialize CAN
    print("[1/4] Initializing CAN bus...")
    ams_can = AMS_CAN()
    sleep(6)
    
    # Auto-detect strips
    print("[2/4] Detecting key strips...")
    for strip_id in range(1, 5):
        version = ams_can.get_version_number(strip_id)
        if version:
            print(f"  ✓ Strip {strip_id} detected (v{version})")
        sleep(0.5)
    
    if len(ams_can.key_lists) == 0:
        print("✗ No strips found. Aborting.")
        ams_can.cleanup()
        return False
    
    print(f"  Found {len(ams_can.key_lists)} strip(s): {ams_can.key_lists}")
    
    # Get all key records from DB grouped by strip
    print("[3/4] Loading key records from database...")
    key_records = (
        session.query(AMS_Keys)
        .filter(AMS_Keys.deletedAt == None)
        .order_by(AMS_Keys.stripId, AMS_Keys.keyPosition)
        .all()
    )
    
    # Group by strip
    strips_in_db = {}
    for key in key_records:
        if key.stripId not in strips_in_db:
            strips_in_db[key.stripId] = []
        strips_in_db[key.stripId].append(key)
    
    print(f"  Found records for {len(strips_in_db)} strip(s) in DB")
    
    # Sync each strip
    print("[4/4] Syncing hardware status to database...")
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
            old_status = key_record.keyPresent
            new_status = 1 if is_present else 0
            key_record.keyPresent = new_status
            
            # Log changes
            if old_status != new_status:
                status_text = "PRESENT" if is_present else "EMPTY"
                print(f"    Pos {position:2d}: {old_status} → {new_status} ({status_text})")
            
            if is_present:
                total_present += 1
            else:
                total_empty += 1
            
            total_synced += 1
            sleep(0.2)
    
    # Commit all changes
    try:
        session.commit()
        print(f"\n✓ Database updated successfully")
    except Exception as e:
        session.rollback()
        print(f"\n✗ Database commit failed: {e}")
        ams_can.cleanup()
        return False
    
    # Summary
    print(f"\n{'='*60}")
    print("SYNC SUMMARY")
    print(f"{'='*60}")
    print(f"Strips checked: {len(ams_can.key_lists)}")
    print(f"Total positions synced: {total_synced}")
    print(f"Keys present: {total_present}")
    print(f"Empty positions: {total_empty}")
    print(f"{'='*60}")
    
    # Cleanup
    ams_can.cleanup()
    return True
