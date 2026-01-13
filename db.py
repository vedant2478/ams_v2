from datetime import datetime
from sqlite3 import IntegrityError
from sqlalchemy.orm import Session
from typing import Optional, Dict , Tuple
from model import (
    AMS_Keys,
    AMS_Users,
    AMS_Activities,
    AMS_Site,
    AMS_Access_Log,
    AMS_Event_Log,
    AMS_Event_Types,
)

from csi_ams.utils.commons import TZ_INDIA


# ==================================================
# EVENT DESCRIPTION
# ==================================================
def get_event_description(session: Session, event_id: int) -> str:
    event = (
        session.query(AMS_Event_Types)
        .filter(AMS_Event_Types.eventId == event_id)
        .one_or_none()
    )
    return event.eventDescription if event else ""


# ==================================================
# ⭐ GENERIC ACCESS + EVENT LOGGER (NEW)
# ==================================================

def log_access_and_event(
    session: Session,
    *,
    event_id: int,
    event_type: int,
    auth_mode: int,
    login_type: str,
    user_id: Optional[int] = None,
    key_id: Optional[int] = None,
    activity_id: Optional[int] = None,
    access_log_updates: Optional[Dict] = None,
) -> dict:
    """
    Universal logger for:
      - AMS_Access_Log
      - AMS_Event_Log

    access_log_updates:
        dict of fields to override on AMS_Access_Log

    Returns:
        {
            "access_log_id": int,
            "event_log_id": int
        }
    """

    # ---------------- ACCESS LOG ----------------
    access_log = AMS_Access_Log(
        signInTime=datetime.now(TZ_INDIA),
        signInMode=auth_mode,
        signInFailed=0,
        signInSucceed=0,
        signInUserId=user_id,
        activityCodeEntryTime=None,
        activityCode=None,
        doorOpenTime=None,
        keysAllowed=None,
        keysTaken=None,
        keysReturned=None,
        doorCloseTime=None,
        event_type_id=event_id,
        is_posted=0,
    )

    if access_log_updates:
        for field, value in access_log_updates.items():
            setattr(access_log, field, value)

    session.add(access_log)
    session.flush()  # get ID without commit

    # ---------------- EVENT LOG ----------------
    event_log = AMS_Event_Log(
        access_log_id=access_log.id,
        userId=user_id or 0,
        keyId=key_id,
        activityId=activity_id,
        eventId=event_id,
        loginType=login_type,
        timeStamp=datetime.now(TZ_INDIA),
        event_type=event_type,
        eventDesc=get_event_description(session, event_id),
        is_posted=0,
    )

    session.add(event_log)
    session.commit()

    return {
        "access_log_id": access_log.id,
        "event_log_id": event_log.id,
    }


# ==================================================
# KEY STATUS (BY PEG ID)
# ==================================================
def set_key_status_by_peg_id(
    session: Session,
    peg_id: int,
    status: int,
):
    """
    status:
        0 = IN
        1 = OUT
    """
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

    print(
        f"[DB] ✅ key_id={key.id} "
        f"(peg_id={peg_id}, strip={key.keyStrip}, pos={key.keyPosition}) "
        f"→ status={status}"
    )

    return key.id


# ==================================================
# GET KEYS FOR ACTIVITY
# ==================================================
def get_keys_for_activity(
    session: Session,
    activity_id: int,
):
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

    return [
        {
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
        }
        for k in keys
    ]


# ==================================================
# SITE NAME
# ==================================================
def get_site_name(session: Session) -> str:
    row = (
        session.query(AMS_Site.siteName)
        .filter(AMS_Site.deletedAt == None)
        .first()
    )
    return row[0] if row and row[0] else "SITE"



# ==================================================
# CARD EXISTS
# ==================================================
def check_card_exists(
    session: Session,
    card_number: str,
):
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


# ==================================================
# VERIFY CARD PIN
# ==================================================
def verify_card_pin(
    session: Session,
    card_number: str,
    pin: str,
) -> bool:
    user = (
        session.query(AMS_Users)
        .filter(
            AMS_Users.cardNo == str(card_number),
            AMS_Users.deletedAt == None,
        )
        .first()
    )
    return bool(user and user.pinCode == str(pin)) 


# return: (success, reason)
# reason in {"ok_assigned", "ok_existing", "no_pin", "conflict"}
def verify_or_assign_card_pin(
    session: Session,
    card_number: str,
    pin: str,
) -> Tuple[bool, str]:
    pin = str(pin)
    card_number = str(card_number)

    user: Optional[AMS_Users] = (
        session.query(AMS_Users)
        .filter(
            AMS_Users.pinCode == pin,
            AMS_Users.deletedAt == None,
        )
        .first()
    )

    if not user:
        return False, "no_pin"

    # already has a card
    if user.cardNo:
        if user.cardNo == card_number:
            return True, "ok_existing"
        else:
            return False, "conflict"  # PIN already bound to some other card

    # no card yet → assign
    user.cardNo = card_number
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return False, "conflict"

    return True, "ok_assigned"


# ==================================================
# USER ACTIVITIES
# ==================================================
def get_user_activities(
    session: Session,
    user_id: int,
):
    activities = (
        session.query(AMS_Activities)
        .filter(AMS_Activities.deletedAt == None)
        .all()
    )

    return [
        {
            "id": a.id,
            "name": a.activityName,
            "code": a.activityCode,
            "time_limit": a.timeLimit,
            "keys": a.keys,
            "key_names": a.keyNames,
        }
        for a in activities
        if a.users and str(user_id) in a.users.split(",")
    ]


# ==================================================
# VERIFY ACTIVITY CODE
# ==================================================
def verify_activity_code(
    session: Session,
    user_id: int,
    activity_code: str,
):
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
