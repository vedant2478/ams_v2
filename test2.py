import sqlite3
import os
from datetime import datetime

# =====================================================
# DB PATH
# =====================================================
BASE_DIR = "D:/vedant/ams_project_v2"   # adjust if needed
DB_PATH = "csiams.dev.sqlite"
def add_user(
    name,
    card_no,
    pin_code=None,
    email=None,
    mobile=None,
    role_id=2,
    is_active=1
):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # ---------------------------------------------
        # CHECK CARD DUPLICATE
        # ---------------------------------------------
        cur.execute("""
            SELECT id FROM users
            WHERE cardNo = ? AND deletedAt IS NULL
        """, (str(card_no),))

        if cur.fetchone():
            print(f"❌ Card {card_no} already exists")
            conn.close()
            return False

        now = datetime.now()

        # ---------------------------------------------
        # INSERT USER (FIXED)
        # ---------------------------------------------
        cur.execute("""
            INSERT INTO users (
                name,
                email,
                mobileNumber,
                cardNo,
                pinCode,
                roleId,
                isActive,
                createdAt,
                updatedAt
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            email,
            mobile,
            str(card_no),
            str(pin_code) if pin_code else None,
            role_id,
            is_active,
            now,
            now
        ))

        conn.commit()
        user_id = cur.lastrowid
        conn.close()

        print("✅ User added successfully")
        print(f"   ID      : {user_id}")
        print(f"   Name    : {name}")
        print(f"   Card No : {card_no}")

        return user_id

    except Exception as e:
        print("❌ Failed to add user")
        print(e)
        return False


if __name__ == "__main__":
    add_user(
        name="Test User",
        card_no=3663674,
        pin_code=10274,
        email="testuser@ams.com",
        mobile="9876543210",
        role_id=2,
        is_active=1
    )
