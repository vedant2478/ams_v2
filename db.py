import sqlite3

import os 

DB_PATH = "csiams.dev.sqlite"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "csiams.dev.sqlite")


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
