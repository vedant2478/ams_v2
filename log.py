import pytz
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# IMPORT YOUR MODELS & CONSTANTS
from csi_ams.model import AMS_Access_Log
from csi_ams.utils.commons import (
    SQLALCHEMY_DATABASE_URI,
    AUTH_MODE_PIN,
    EVENT_LOGIN_SUCCEES,
)

def test_login_access_log():
    print("=== TEST : LOGIN ACCESS LOG ===")

    # Timezone
    TZ_INDIA = pytz.timezone("Asia/Kolkata")

    # DB connection
    engine = create_engine(SQLALCHEMY_DATABASE_URI)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Create test access log
        access_log = AMS_Access_Log(
            signInTime=datetime.now(TZ_INDIA),
            signInMode=AUTH_MODE_PIN,     # PIN login
            signInFailed=0,
            signInSucceed=1,
            signInUserId=1,               # TEST USER ID
            activityCodeEntryTime=None,
            activityCode=None,
            doorOpenTime=None,
            keysAllowed=None,
            keysTaken=None,
            keysReturned=None,
            doorCloseTime=None,
            event_type_id=EVENT_LOGIN_SUCCEES,
            is_posted=0,
        )

        session.add(access_log)
        session.commit()

        print("✅ Access log inserted successfully")
        print(f"🆔 Access Log ID : {access_log.id}")

    except Exception as e:
        session.rollback()
        print("❌ Failed to insert access log")
        print(e)

    finally:
        session.close()

if __name__ == "__main__":
    test_login_access_log()
