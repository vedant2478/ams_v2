from datetime import datetime
from typing import Optional, Dict
from sqlalchemy.orm import Session

from model import (
    AMS_Access_Log,
    AMS_Event_Log,
    AMS_Event_Types,
)

from csi_ams.utils.commons import TZ_INDIA


# ==================================================
# ACCESS + EVENT LOG HELPER
# ==================================================
def log_access_and_event(
    session: Session,
    *,
    event_id: int,
    event_type: int,
    auth_mode: Optional[int] = None,
    login_type: Optional[str] = None,
    user_id: Optional[int] = None,
    key_id: Optional[int] = None,
    activity_id: Optional[int] = None,
    access_log_updates: Optional[Dict] = None,
):
    """
    Generic helper to create AMS_Access_Log + AMS_Event_Log.

    access_log_updates:
        Dict of fields to override in AMS_Access_Log
        Example:
            {
                "signInFailed": 1,
                "signInSucceed": 0,
                "keysTaken": "[1,2]",
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

    # Apply dynamic updates
    if access_log_updates:
        for field, value in access_log_updates.items():
            if hasattr(access_log, field):
                setattr(access_log, field, value)

    session.add(access_log)
    session.flush()  # get access_log.id without committing

    # ---------------- EVENT DESCRIPTION ----------------
    event_type_row = (
        session.query(AMS_Event_Types)
        .filter(AMS_Event_Types.eventId == event_id)
        .one_or_none()
    )
    event_desc = event_type_row.eventDescription if event_type_row else ""

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
        eventDesc=event_desc,
        is_posted=0,
    )

    session.add(event_log)
    session.commit()

    return {
        "access_log_id": access_log.id,
        "event_log_id": event_log.id,
    }
