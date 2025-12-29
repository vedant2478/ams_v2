import sqlite3

import os 

DB_PATH = "csiams.dev.sqlite"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "csiams.dev.sqlite")


def toggle_key_status_and_get_position(key_id):
    """
    Toggle keyStatus (0 <-> 1) for given key, and return updated row
    including strip and position.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get current status and position info
    cur.execute("""
        SELECT id, keyName, description, color, keyLocation, keyStatus,
               keyAtDoor, keyStrip, keyPosition
        FROM keys
        WHERE id = ? AND deletedAt IS NULL
    """, (key_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return None

    current_status = row[5] or 0
    new_status = 0 if current_status == 1 else 1

    # Update status
    cur.execute("""
        UPDATE keys
        SET keyStatus = ?
        WHERE id = ?
    """, (new_status, key_id))
    conn.commit()
    conn.close()

    return {
        "id": row[0],
        "name": row[1],
        "description": row[2],
        "color": row[3],
        "location": row[4],
        "status": new_status,
        "door": row[6],
        "strip": row[7],
        "position": row[8],
    }


def toggle_key_status_by_peg_id(peg_id):
    """
    Toggle keyStatus using peg_id coming from CAN hardware.
    peg_id == hardware key fob ID
    """

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Map peg_id -> key record
    cur.execute("""
        SELECT id, keyStatus
        FROM keys
        WHERE peg_id = ? AND deletedAt IS NULL
    """, (int(peg_id),))

    row = cur.fetchone()
    if not row:
        print(f"[DB] ❌ No key found for peg_id={peg_id}")
        conn.close()
        return None

    key_id, current_status = row
    new_status = 0 if current_status == 1 else 1

    cur.execute("""
        UPDATE keys
        SET keyStatus = ?
        WHERE id = ?
    """, (new_status, key_id))

    conn.commit()
    conn.close()

    print(f"[DB] ✅ Updated key_id={key_id} → status={new_status}")
    return key_id


def get_site_name():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT siteName FROM sites LIMIT 1;")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "SITE"

def check_card_exists(card_number):
    """Check if card exists in database and return user details"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Query to check card existence in users table
        cur.execute("""
            SELECT id, name, email, mobileNumber, cardNo, pinCode, roleId, isActive
            FROM users 
            WHERE cardNo = ? AND deletedAt IS NULL
        """, (str(card_number),))
        
        row = cur.fetchone()
        conn.close()
        
        if row:
            return {
                "exists": True,
                "id": row[0],
                "name": row[1],
                "email": row[2],
                "mobile": row[3],
                "card_number": row[4],
                "pin_code": row[5],
                "role_id": row[6],
                "is_active": row[7],
                "pin_required": bool(row[5])  # PIN required if pinCode is set
            }
        else:
            return {"exists": False}
            
    except Exception as e:
        print(f"Error checking card: {e}")
        return {"exists": False, "error": str(e)}

def verify_card_pin(card_number, pin):
    """Verify if PIN matches for the card"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT pinCode 
            FROM users 
            WHERE cardNo = ? AND deletedAt IS NULL
        """, (str(card_number),))
        
        row = cur.fetchone()
        conn.close()
        
        if row and row[0] == str(pin):
            return True
        return False
        
    except Exception as e:
        print(f"Error verifying PIN: {e}")
        return False

def get_user_by_card(card_number):
    """Get complete user info by card number"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT * FROM users 
            WHERE cardNo = ? AND deletedAt IS NULL
        """, (str(card_number),))
        
        row = cur.fetchone()
        conn.close()
        
        return row
        
    except Exception as e:
        print(f"Error getting user: {e}")
        return None

def get_user_activities(user_id):
    """Get all activities assigned to a user"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, activityName, activityCode, timeLimit, keys, keyNames, users
            FROM activities 
            WHERE deletedAt IS NULL
        """)
        
        all_activities = cur.fetchall()
        conn.close()
        
        # Filter activities where user is assigned
        user_activities = []
        for activity in all_activities:
            users_list = activity[6]  # users column
            if users_list and str(user_id) in users_list.split(','):
                user_activities.append({
                    'id': activity[0],
                    'name': activity[1],
                    'code': activity[2],
                    'time_limit': activity[3],
                    'keys': activity[4],
                    'key_names': activity[5]
                })
        
        return user_activities
        
    except Exception as e:
        print(f"Error getting user activities: {e}")
        return []

def verify_activity_code(user_id, activity_code):
    """Verify if activity code is valid for the user"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, activityName, activityCode, timeLimit, keys, keyNames, users
            FROM activities 
            WHERE activityCode = ? AND deletedAt IS NULL
        """, (str(activity_code),))
        
        activity = cur.fetchone()
        conn.close()
        
        if not activity:
            return {"valid": False, "message": "Activity code not found"}
        
        # Check if user is assigned to this activity
        users_list = activity[6]
        if users_list and str(user_id) in users_list.split(','):
            return {
                "valid": True,
                "id": activity[0],
                "name": activity[1],
                "code": activity[2],
                "time_limit": activity[3],
                "keys": activity[4],
                "key_names": activity[5]
            }
        else:
            return {"valid": False, "message": "You are not assigned to this activity"}
        
    except Exception as e:
        print(f"Error verifying activity code: {e}")
        return {"valid": False, "message": str(e)}

def get_keys_for_activity(activity_id):
    """Get detailed key information for an activity"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Get activity keys
        cur.execute("""
            SELECT keys, keyNames
            FROM activities 
            WHERE id = ? AND deletedAt IS NULL
        """, (activity_id,))
        
        activity = cur.fetchone()
        
        if not activity or not activity[0]:
            conn.close()
            return []
        
        key_ids = [k.strip() for k in activity[0].split(',')]
        key_names_from_activity = [k.strip() for k in activity[1].split(',')] if activity[1] else []
        
        # Get detailed key info from keys table
        keys_list = []
        for i, key_id in enumerate(key_ids):
            cur.execute("""
                SELECT id, keyName, description, color, keyLocation, keyStatus, 
                       keyAtDoor, keyStrip, keyPosition
                FROM keys 
                WHERE id = ? AND deletedAt IS NULL
            """, (key_id,))
            
            key_row = cur.fetchone()
            
            if key_row:
                keys_list.append({
                    'id': key_row[0],
                    'name': key_row[1],
                    'description': key_row[2],
                    'color': key_row[3],
                    'location': key_row[4],
                    'status': key_row[5],  # 0=available, 1=taken
                    'door': key_row[6],
                    'strip': key_row[7],
                    'position': key_row[8]
                })
            else:
                # Key not found in keys table, use name from activity
                key_name = key_names_from_activity[i] if i < len(key_names_from_activity) else f"Key {key_id}"
                keys_list.append({
                    'id': key_id,
                    'name': key_name,
                    'description': '',
                    'color': '',
                    'location': '',
                    'status': 0,
                    'door': None,
                    'strip': None,
                    'position': None
                })
        
        conn.close()
        return keys_list
        
    except Exception as e:
        print(f"Error getting keys for activity: {e}")
        return []
