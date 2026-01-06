from sqlalchemy import Column, Integer, String, ForeignKey, Table, BINARY, func, and_
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.sqltypes import SMALLINT, DateTime, Time
from datetime import date, datetime, timedelta
import pytz

Base = declarative_base()

AUTH_MODE_PIN = 1
AUTH_MODE_CARD = 2

AUTH_RESULT_SUCCESS = 0
AUTH_RESULT_FAILED = 1

ADMIN_PIN = "99999"

ACTIVITY_ALLOWED = 0
ACTIVITY_ERROR_USER_INVALID = 1
ACTIVITY_ERROR_TIME_INVALID = 2
ACTIVITY_ERROR_WEEKDAY_INVALID = 3
ACTIVITY_ERROR_FREQUENCY_EXCEEDED = 4
ACTIVITY_ERROR_CODE_INCORRECT = 5

EVENT_LOGIN_SUCCEES = 1
EVENT_LOGIN_FAILED = 2
EVENT_ACTIVITY_CODE_CORRECT = 3
EVENT_ACTIVITY_CODE_WRONG = 4
EVENT_ACTIVITY_CODE_NOT_ALLOWED = 5
EVENT_DOOR_OPEN = 6
EVENT_DOOR_CLOSED = 7
EVENT_DOOR_OPENED_TOO_LONG = 8
EVENT_KEY_TAKEN_CORRECT = 9
EVENT_KEY_TAKEN_WRONG = 10
EVENT_KEY_RETURNED_RIGHT_SLOT = 11
EVENT_KEY_RETURNED_WRONG_SLOT = 12
EVENT_ACTIVITY_CODE_TIMEOUT = 13
EVENT_EMERGENCY_DOOR_OPEN = 14
EVENT_PEG_REGISTERATION = 15

EVENT_TYPE_EVENT = 1
EVENT_TYPE_ALARM = 2

SLOT_STATUS_KEY_NOT_PRESENT = 0
SLOT_STATUS_KEY_PRESENT_RIGHT_SLOT = 1
SLOT_STATUS_KEY_PRESENT_WRONG_SLOT = 2


tz_IN = pytz.timezone("Asia/Kolkata")

site_cabinet = Table(
    "site_cabinet",
    Base.metadata,
    Column("site_id", Integer, ForeignKey("sites.id")),
    Column("cabinet_id", Integer, ForeignKey("cabinets.id")),
)


class AMS_Site(Base):
    __tablename__ = "sites"
    id = Column(Integer, primary_key=True)
    siteName = Column(String)
    street = Column(String)
    district = Column(String)
    city = Column(String)
    state = Column(String)
    pinCode = Column(Integer)
    contactNumber = Column(String)
    registerationNumber = Column(String)
    createdAt = Column(DateTime)
    updatedAt = Column(DateTime)
    deletedAt = Column(DateTime)
    cabinet = relationship("AMS_Cabinet", back_populates="site", uselist=False)


class AMS_Cabinet(Base):
    __tablename__ = "cabinets"
    id = Column(Integer, primary_key=True)
    cabinetName = Column(String)
    doors = Column(Integer)
    strips = Column(Integer)
    location = Column(String)
    timeoutForDoor = Column(Integer)
    timeoutForBattery = Column(Integer)
    ipAddress = Column(String)
    subnetMask = Column(String)
    gateway = Column(String)
    primaryDNS = Column(String)
    secondaryDNS = Column(String)
    createdAt = Column(DateTime)
    updatedAt = Column(DateTime)
    siteId = Column(Integer, ForeignKey("sites.id"))
    site = relationship("AMS_Site", back_populates="cabinet")
    keys = relationship("AMS_Keys", back_populates="cabinet")
    users = relationship("AMS_Users", back_populates="cabinet")
    roles = relationship("AMS_Roles", back_populates="cabinet")


cabinet_keys = Table(
    "cabinet_keys",
    Base.metadata,
    Column("cabinet_id", Integer, ForeignKey("cabinets.id")),
    Column("key_id", Integer, ForeignKey("keys.id")),
)


class AMS_Roles(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    roleName = Column(String)
    cabinetId = Column(Integer, ForeignKey("cabinets.id"))
    cabinet = relationship("AMS_Cabinet", back_populates="roles")


class AMS_emergency_door_open(Base):
    __tablename__ = "emergency_doors"
    id = Column(Integer, primary_key=True)
    emergency_status = Column(SMALLINT)
    userId = Column(Integer)

    def is_emergency_req_received(self, session):
        return (
            session.query(AMS_emergency_door_open)
            .filter(AMS_emergency_door_open.emergency_status == 1)
            .first()
        )


class AMS_Keys(Base):
    __tablename__ = "keys"
    id = Column(Integer, primary_key=True)
    keyName = Column(String)
    description = Column(String)
    color = Column(String)
    keyAtDoor = Column(Integer)
    keyStrip = Column(Integer)
    keyPosition = Column(Integer)
    keyLocation = Column(String)
    keyStatus = Column(SMALLINT)
    keyTakenBy = Column(String)
    current_pos_door_id = Column(Integer)
    current_pos_strip_id = Column(Integer)
    current_pos_slot_no = Column(Integer)
    keyTakenAtTime = Column(DateTime)
    peg_id = Column(Integer)
    cabinetId = Column(Integer, ForeignKey("cabinets.id"))
    cabinet = relationship("AMS_Cabinet", back_populates="keys")
    keyTakenByUser = Column(String)
    createdAt = Column(DateTime)
    updatedAt = Column(DateTime)
    deletedAt = Column(DateTime)
    is_critical = Column(Integer)
    keyTimeout = Column(Integer)
    keyAck = Column(DateTime)


class AMS_Key_Pegs(Base):
    __tablename__ = "key_pegs"
    peg_id = Column(Integer, primary_key=True)
    keylist_no = Column(Integer)
    keyslot_no = Column(Integer)


cabinet_users = Table(
    "cabinet_users",
    Base.metadata,
    Column("cabinet_id", Integer, ForeignKey("cabinets.id")),
    Column("user_id", Integer, ForeignKey("users.id")),
)


class AMS_Users(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)
    mobileNumber = Column(String)
    validityFrom = Column(DateTime)
    validityTo = Column(DateTime)
    pinCode = Column(String)
    roleId = Column(Integer)
    lastLoginDate = Column(DateTime)
    isActive = Column(String)
    isActiveInt = Column(SMALLINT)
    cabinetId = Column(Integer, ForeignKey("cabinets.id"))
    createdAt = Column(DateTime)
    updatedAt = Column(DateTime)
    deletedAt = Column(DateTime)
    cardNo = Column(String)
    cabinet = relationship("AMS_Cabinet", back_populates="users")
    fpTemplate = Column(BINARY)

    def get_user_id(self, session, auth_mode, **kwargs):

        dic_result = {}
        if auth_mode == AUTH_MODE_PIN:
            pin_no = kwargs["pin_no"]
            print(f"here with pin no: {pin_no}")
            recordset = (
                session.query(AMS_Users)
                .filter(and_(AMS_Users.pinCode == pin_no, AMS_Users.deletedAt == None))
                .first()
            )
            print(f"recordset is : {recordset}")
            if recordset:
                if recordset.isActive == "1":
                    time_now = datetime.now() + timedelta(minutes=330)
                    if (time_now >= recordset.validityFrom) and (
                        time_now <= recordset.validityTo
                    ):
                        dic_result = {
                            "ResultCode": AUTH_RESULT_SUCCESS,
                            "id": recordset.id,
                            "name": recordset.name,
                            "roleId": recordset.roleId,
                        }
                        return dic_result
                    else:
                        dic_result = {
                            "ResultCode": AUTH_RESULT_FAILED,
                            "Message": "Validity expired",
                        }
                        return dic_result
                else:
                    dic_result = {
                        "ResultCode": AUTH_RESULT_FAILED,
                        "Message": "User In-active",
                    }
                    return dic_result
            else:
                dic_result = {
                    "ResultCode": AUTH_RESULT_FAILED,
                    "Message": "Invalid PIN-No",
                }
                return dic_result

        elif auth_mode == AUTH_MODE_CARD:
            card_no = kwargs["card_no"]
            print(type(card_no))
            recordset = (
                session.query(AMS_Users)
                .filter(AMS_Users.cardNo == str(card_no), AMS_Users.deletedAt == None)
                .first()
            )
            print(recordset)
            if recordset:
                if recordset.isActive == "1":
                    time_now = datetime.now() + timedelta(minutes=330)
                    if (time_now >= recordset.validityFrom) and (
                        time_now <= recordset.validityTo
                    ):
                        dic_result = {
                            "ResultCode": AUTH_RESULT_SUCCESS,
                            "id": recordset.id,
                            "name": recordset.name,
                            "roleId": recordset.roleId,
                        }
                        return dic_result
                    else:
                        dic_result = {
                            "ResultCode": AUTH_RESULT_FAILED,
                            "Message": "Validity expired",
                        }
                        return dic_result
                else:
                    dic_result = {
                        "ResultCode": AUTH_RESULT_FAILED,
                        "Message": "User In-active",
                    }
                    return dic_result
            else:
                dic_result = {
                    "ResultCode": AUTH_RESULT_FAILED,
                    "Message": "Invalid PIN/Card",
                }
                return dic_result


class AMS_Activities(Base):
    __tablename__ = "activities"
    id = Column(Integer, primary_key=True)
    activityName = Column(String)
    activityCode = Column(String)
    timeLimit = Column(Integer)
    frequency = Column(Integer)
    timeSlotFrom = Column(Time)
    timeSlotTo = Column(Time)
    weekDays = Column(String)
    keys = Column(String)
    keyNames = Column(String)
    users = Column(String)
    userNames = Column(String)
    createdAt = Column(DateTime)
    updatedAt = Column(DateTime)
    deletedAt = Column(DateTime)

    def get_keys_allowed(self, session, userid, activity_code, access_time):

        dic_result = {}
        recordset = (
            session.query(AMS_Activities)
            .filter(AMS_Activities.activityCode == activity_code)
            .first()
        )

        if recordset:
            user_exist = str(userid) in str(recordset.users).split(",")
            if user_exist:
                allowed_now = (access_time.time() >= recordset.timeSlotFrom) and (
                    access_time.time() <= recordset.timeSlotTo
                )
                if allowed_now:
                    allowed_today = str(access_time.today().weekday()) in str(
                        recordset.weekDays
                    ).split(",")
                    if allowed_today:
                        recordCount = (
                            session.query(AMS_Access_Log)
                            .filter(
                                AMS_Access_Log.activityCode == activity_code,
                                func.date(AMS_Access_Log.activityCodeEntryTime)
                                == date.today(),
                                AMS_Access_Log.keysTaken != "[]",
                            )
                            .count()
                        )
                        if (
                            recordCount <= recordset.frequency
                            or recordset.frequency == 0
                        ):
                            dic_result = {
                                "ResultCode": ACTIVITY_ALLOWED,
                                "Message": str(recordset.keys),
                                "Description": recordset.activityName,
                            }
                            return dic_result

                        else:
                            dic_result = {
                                "ResultCode": ACTIVITY_ERROR_FREQUENCY_EXCEEDED,
                                "Message": "Frequency exceed",
                            }
                            return dic_result
                    else:
                        dic_result = {
                            "ResultCode": ACTIVITY_ERROR_WEEKDAY_INVALID,
                            "Message": "Not allowed today",
                        }
                        return dic_result
                else:
                    dic_result = {
                        "ResultCode": ACTIVITY_ERROR_TIME_INVALID,
                        "Message": "Wrong time slot",
                    }
                    return dic_result
            else:
                dic_result = {
                    "ResultCode": ACTIVITY_ERROR_USER_INVALID,
                    "Message": "User not allowed",
                }
                return dic_result
        else:
            dic_result = {
                "ResultCode": ACTIVITY_ERROR_CODE_INCORRECT,
                "Message": "Wrong Act. Code",
            }
            return dic_result


class AMS_Access_Log(Base):
    __tablename__ = "access_log"
    id = Column(Integer, primary_key=True)
    signInTime = Column(DateTime)
    signInMode = Column(SMALLINT)
    signInFailed = Column(SMALLINT)
    signInSucceed = Column(SMALLINT)
    signInUserId = Column(Integer)
    activityCodeEntryTime = Column(DateTime)
    activityCode = Column(Integer)
    doorOpenTime = Column(DateTime)
    keysAllowed = Column(String)
    keysTaken = Column(String)
    keysReturned = Column(String)
    doorCloseTime = Column(DateTime)
    event_type_id = Column(Integer)
    is_posted = Column(Integer)


class AMS_Event_Types(Base):
    __tablename__ = "event_types"
    eventId = Column(Integer, primary_key=True)
    eventMessage = Column(String)
    eventType = Column(SMALLINT)
    eventDescription = Column(String)


class AMS_Event_Log(Base):
    __tablename__ = "eventlogs"
    id = Column(Integer, primary_key=True)
    access_log_id = Column(Integer)
    userId = Column(Integer)
    keyId = Column(Integer)
    activityId = Column(Integer)
    eventId = Column(Integer)
    loginType = Column(String)
    timeStamp = Column(DateTime)
    event_type = Column(SMALLINT)
    eventDesc = Column(String)
    acknowledgeStatus = Column(Integer)
    acknowledgeAt = Column(DateTime)
    is_posted = Column(Integer)


class AMS_Activity_Progress_Status(Base):
    __tablename__ = "activity_progress_status"
    id = Column(Integer, primary_key=True)
    is_active = Column(Integer)
