from datetime import datetime
from sqlalchemy.orm import Session

from db_core import SessionLocal
from model import (
    AMS_Keys,
    AMS_Users,
    AMS_Activities,
    AMS_Site,
)

# --------------------------------------------------
# SESSION HELPER
# --------------------------------------------------
def get_session() -> Session:
    return SessionLocal()


# --------------------------------------------------
# KEY STATUS (BY PEG ID)
# --------------------------------------------------
def set_key_status_by_peg_id(peg_id: int, status: int):
    """
    status:
        0 = IN
        1 = OUT
    """
    session = get_session()
    try:
        key = (
            session.query(AMS_Keys)
            .filter(
                AMS_Keys.peg_id == peg_id,
                AMS_Keys.deletedAt == None,
            )
            .first()
        )

        if not key:
            print(f"[DB] ❌ No key found for peg_id={peg_id}")
            return None

        key.keyStatus = status
        key.updatedAt = datetime.now()

        session.commit()

        print(
            f"[DB] ✅ key_id={key.id} "
            f"(peg_id={peg_id}, strip={key.keyStrip}, pos={key.keyPosition}) "
            f"→ status={status}"
        )
        return key.id

    except Exception as e:
        session.rollback()
        print("[DB][ERROR] set_key_status_by_peg_id:", e)
        return None

    finally:
        session.close()


# --------------------------------------------------
# GET KEYS FOR ACTIVITY
# --------------------------------------------------
def get_keys_for_activity(activity_id: int):
    session = get_session()
    try:
        activity = (
            session.query(AMS_Activities)
            .filter(
                AMS_Activities.id == activity_id,
                AMS_Activities.deletedAt == None,
            )
            .first()
        )

        if not activity or not activity.keys:
            return []

        key_ids = [int(k) for k in activity.keys.split(",")]

        keys = (
            session.query(AMS_Keys)
            .filter(
                AMS_Keys.id.in_(key_ids),
                AMS_Keys.deletedAt == None,
            )
            .all()
        )

        return [{
            "id": k.id,
            "name": k.keyName,
            "description": k.description,
            "color": k.color,
            "location": k.keyLocation,
            "status": k.keyStatus,
            "door": k.keyAtDoor,
            "strip": k.keyStrip,
            "position": k.keyPosition,
            "peg_id": k.peg_id,
        } for k in keys]

    except Exception as e:
        print("[DB][ERROR] get_keys_for_activity:", e)
        return []

    finally:
        session.close()


# --------------------------------------------------
# SITE NAME
# --------------------------------------------------
def get_site_name():
    session = get_session()
    try:
        site = session.query(AMS_Site).first()
        return site.siteName if site else "SITE"
    finally:
        session.close()


# --------------------------------------------------
# CARD EXISTS
# --------------------------------------------------
def check_card_exists(card_number: str):
    session = get_session()
    try:
        user = (
            session.query(AMS_Users)
            .filter(
                AMS_Users.cardNo == str(card_number),
                AMS_Users.deletedAt == None,
            )
            .first()
        )

        if not user:
            return {"exists": False}

        return {
            "exists": True,
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "mobile": user.mobileNumber,
            "card_number": user.cardNo,
            "pin_code": user.pinCode,
            "role_id": user.roleId,
            "is_active": user.isActive,
            "pin_required": bool(user.pinCode),
        }

    finally:
        session.close()


# --------------------------------------------------
# VERIFY CARD PIN
# --------------------------------------------------
def verify_card_pin(card_number: str, pin: str) -> bool:
    session = get_session()
    try:
        user = (
            session.query(AMS_Users)
            .filter(
                AMS_Users.cardNo == str(card_number),
                AMS_Users.deletedAt == None,
            )
            .first()
        )
        return bool(user and user.pinCode == str(pin))
    finally:
        session.close()


# --------------------------------------------------
# USER ACTIVITIES
# --------------------------------------------------
def get_user_activities(user_id: int):
    session = get_session()
    try:
        activities = (
            session.query(AMS_Activities)
            .filter(AMS_Activities.deletedAt == None)
            .all()
        )

        return [{
            "id": a.id,
            "name": a.activityName,
            "code": a.activityCode,
            "time_limit": a.timeLimit,
            "keys": a.keys,
            "key_names": a.keyNames,
        } for a in activities if a.users and str(user_id) in a.users.split(",")]

    finally:
        session.close()


# --------------------------------------------------
# VERIFY ACTIVITY CODE
# --------------------------------------------------
def verify_activity_code(user_id: int, activity_code: str):
    session = get_session()
    try:
        activity = (
            session.query(AMS_Activities)
            .filter(
                AMS_Activities.activityCode == str(activity_code),
                AMS_Activities.deletedAt == None,
            )
            .first()
        )

        if not activity:
            return {"valid": False, "message": "Activity code not found"}

        if activity.users and str(user_id) in activity.users.split(","):
            return {
                "valid": True,
                "id": activity.id,
                "name": activity.activityName,
                "code": activity.activityCode,
                "time_limit": activity.timeLimit,
                "keys": activity.keys,
                "key_names": activity.keyNames,
            }

        return {"valid": False, "message": "User not assigned"}

    finally:
        session.close()
