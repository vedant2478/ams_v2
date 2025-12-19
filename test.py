
import sqlite3

conn = sqlite3.connect('csiams.dev.sqlite')
cur = conn.cursor()

# Get test user ID
cur.execute("SELECT id FROM users WHERE cardNo = ?", ('3663674',))
test_user = cur.fetchone()
test_user_id = test_user[0] if test_user else None

if test_user_id:
    print(f"Test user ID: {test_user_id}")
    
    # Assign activities 17 (Code 54) and 1 (Code 11) to test user
    # Update activities to include test user in users list
    activities_to_assign = [
        (17, '54', 'Surprise Checks by Visiting RBML or S1 Officials'),
        (1, '11', 'Sampling for daily density check'),
        (2, '12', 'Dispenser Measure Check')
    ]
    
    for activity_id, code, name in activities_to_assign:
        cur.execute("SELECT users FROM activities WHERE id = ?", (activity_id,))
        result = cur.fetchone()
        
        if result:
            current_users = result[0] if result[0] else ""
            # Add test user if not already in list
            if str(test_user_id) not in current_users.split(','):
                new_users = f"{current_users},{test_user_id}" if current_users else str(test_user_id)
                cur.execute("UPDATE activities SET users = ? WHERE id = ?", (new_users, activity_id))
                print(f"✓ Assigned activity {code} - {name}")
    
    conn.commit()
    print("\n✓ Activities assigned to test user")
    
    # Verify
    print("\n=== Test user activities ===")
    cur.execute("""
        SELECT id, activityName, activityCode 
        FROM activities 
        WHERE users LIKE ? AND deletedAt IS NULL
    """, (f'%{test_user_id}%',))
    
    activities = cur.fetchall()
    for a in activities:
        print(f"Code {a[2]}: {a[1]}")
else:
    print("Test user not found!")

conn.close()
