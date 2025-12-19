import os
import requests
import json
import re
import schedule
import ctypes
import pytz
import logging
from time import sleep
from datetime import datetime
from model import *
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from threading import Lock

TZ_INDIA = pytz.timezone("Asia/Kolkata")
COMMUNICATION_ADDRESS = "https://amsenterprise.jiobp.com"
# COMMUNICATION_ADDRESS = "10.131.95.251"
SQLALCHEMY_DATABASE_URI = "sqlite:////home/ams-core/csiams.dev.sqlite"
LOGFILE_PATH = "/home/apicalls_logfile.log"
PORT = ""
TIMEOUT = 10
mutex = Lock()
logger = None
CURRENT_ACTIVITY_IDS = []


def post_data_fetch_result(data, url, fn_name):
    cnt = 1
    try:
        while True and cnt <= 3:
            try:
                res = requests.post(url, json=data, timeout=TIMEOUT)
                break
            except Exception as e:
                print(e)
                sleep(10)
                cnt += 1
        if cnt == 3:
            logger.error("threshold reached and server didn't respond!")
            print("threshold reached and server didn't respond!")
            return None
        print(f"Response from {fn_name}")
        return res.json()
    except Exception as e:
        logger.error(e)
        print("exception reason => ", e)
    return None


def get_cabinet_id(session):
    cabinet = session.query(AMS_Cabinet).first()
    if cabinet:
        return str(cabinet.id)
    return None


def get_cabinet_ip(session):
    cabinet = session.query(AMS_Cabinet).first()
    if cabinet:
        return str(cabinet.ipAddress)
    return None


def get_door_status(lib_KeyboxLock):
    return lib_KeyboxLock.getDoorSensorStatus1()


def post_cabinet_status(session, lib_KeyboxLock):
    is_activity = (
        session.query(AMS_Activity_Progress_Status)
        .filter(AMS_Activity_Progress_Status.id == 1)
        .first()
    )
    if is_activity.is_active:
        print("execution stopped due to cabinet activities going on")
        return
    mutex.acquire()
    try:
        CABINET_ID = get_cabinet_ip(session)
        RO_NAME = session.query(AMS_Site).first().siteName
        RO_CODE = session.query(AMS_Cabinet).first().cabinetName
        LAST_PING_TS = str(datetime.now(tz=TZ_INDIA))
        latest_event = (
            session.query(AMS_Event_Log)
            .order_by(AMS_Event_Log.timeStamp.desc())
            .limit(1)
            .first()
        )
        LAST_KEY_ACTIVITY = str(latest_event.timeStamp)
        last_logged_in = (
            session.query(AMS_Access_Log)
            .filter(AMS_Access_Log.signInSucceed == 1)
            .order_by(AMS_Access_Log.signInTime.desc())
            .limit(1)
            .first()
        )
        LAST_LOGIN = str(last_logged_in.signInTime)
        MAIN_DOOR_STATUS = get_door_status(lib_KeyboxLock)

        # Reading battery% from bms.dat text file
        BATTERY_CHARGE_PC = -1
        with open('bms.dat', 'r') as fBMS:
            strData = fBMS.readline()
            arrData = strData.split(',')
            if arrData:
                BATTERY_CHARGE_PC = int(arrData[1])
            fBMS.close()

        cabinet_status_data = {
            "CABINET_ID": CABINET_ID,
            "RO_NAME": RO_NAME,
            "RO_CODE": RO_CODE,
            "LAST_PING_TS": LAST_PING_TS,
            "LAST_KEY_ACTIVITY": LAST_KEY_ACTIVITY,
            "LAST_LOGIN": LAST_LOGIN,
            "BATTERY_CHARGE_PC": str(BATTERY_CHARGE_PC),
            "MAIN_DOOR_STATUS": MAIN_DOOR_STATUS,
        }
        print(
            post_data_fetch_result(
                cabinet_status_data,
                f"{COMMUNICATION_ADDRESS}/api/Cabinet/AMSC-Cabinet-Status",
                post_cabinet_status.__name__,
            )
        )
    except Exception as e:
        logger.error(e)
        print("exception reason inside code => ", e)
    mutex.release()


def post_ams_users(session):
    is_activity = (
        session.query(AMS_Activity_Progress_Status)
        .filter(AMS_Activity_Progress_Status.id == 1)
        .first()
    )
    if is_activity.is_active:
        print("execution stopped due to cabinet activities going on")
        return
    mutex.acquire()
    try:
        users_data = []
        CABINET_ID = get_cabinet_ip(session)
        users = session.query(AMS_Users).all()
        for user in users:
            try:
                user_id = int(user.id)
                name = user.name if user.name else None
                email = user.email if user.email else None
                mobileNumber = str(user.mobileNumber) if user.mobileNumber else None
                validityFrom = (
                    str(user.validityFrom.date()) if user.validityFrom else None
                )
                validityTo = str(user.validityTo.date()) if user.validityTo else None
                pinCode = str(user.pinCode) if user.pinCode else None
                roleId = int(user.roleId) if user.roleId else 2
                isActive = str(user.isActive) if user.isActive else "1"
                cabinetId = CABINET_ID
                cardNo = str(user.cardNo) if user.cardNo else None
                lastLoginDate = str(user.lastLoginDate) if user.lastLoginDate else None
                user_data = {
                    "CABINET_ID": cabinetId,
                    "USER_ID": user_id,
                    "USER_ROLE_ID": roleId,
                    "USER_NAME": name,
                    "USER_EMAIL": email,
                    "USER_MOBILE": mobileNumber,
                    "USER_VALIDITY_FROM": validityFrom,
                    "USER_VALIDITY_TO": validityTo,
                    "USER_AMS_PIN": pinCode,
                    "USER_IS_ACTIVE": isActive,
                    "USER_CARD_NO": cardNo,
                    "USER_FP_TEMPLATE": None,
                    "USER_LAST_LOGIN_TIMESTAMP": lastLoginDate,
                }
                print(user_data)
                users_data.append(user_data)
            except Exception as e:
                logger.error(e)
                print("exception reason inside code => ", e)
                continue
        print(
            post_data_fetch_result(
                users_data,
                f"{COMMUNICATION_ADDRESS}/api/Cabinet/AMSC-Config-Users",
                post_ams_users.__name__,
            )
        )
    except Exception as e:
        logger.error(e)
        print("exception reason inside code => ", e)
    mutex.release()


def post_ams_event_logs(session):
    global CURRENT_ACTIVITY_IDS
    is_activity = (
        session.query(AMS_Activity_Progress_Status)
        .filter(AMS_Activity_Progress_Status.id == 1)
        .first()
    )
    if is_activity.is_active:
        print("execution stopped due to cabinet activities going on")
        return
    mutex.acquire()
    CABINET_ID = get_cabinet_ip(session)

    event_logs = (
        session.query(AMS_Event_Log)
        .filter(AMS_Event_Log.is_posted == 0)
        .filter(AMS_Event_Log.access_log_id.in_(tuple(CURRENT_ACTIVITY_IDS)))
        .all()
    )

    CURRENT_ACTIVITY_IDS = []
    event_logs_data = []

    for elog in event_logs:
        try:
            EVENT_LOG_ID = elog.id
            ACCESS_LOG_ID = elog.access_log_id
            EVENT_ID = elog.eventId
            event_type = (
                session.query(AMS_Event_Types)
                .filter(AMS_Event_Types.eventId == elog.eventId)
                .first()
            )
            EVENT_DESC = (
                str(event_type.eventDescription)
                if event_type.eventDescription
                else None
            )
            LOGIN_TYPE = str(elog.loginType) if elog.loginType else None
            EVENT_TS = str(elog.timeStamp)
            EVENT_TYPE = elog.event_type
            ACK_STATUS = str(elog.acknowledgeStatus) if elog.acknowledgeStatus else None
            ACK_TIME = str(elog.acknowledgeAt) if elog.acknowledgeAt else None
            log_data = {
                "CABINET_ID": CABINET_ID,
                "EVENT_LOG_ID": EVENT_LOG_ID,
                "ACCESS_LOG_ID": ACCESS_LOG_ID,
                "EVENT_ID": EVENT_ID,
                "EVENT_DESC": EVENT_DESC,
                "LOGIN_TYPE": LOGIN_TYPE,
                "EVENT_TS": EVENT_TS,
                "EVENT_TYPE": EVENT_TYPE,
                "ACK_STATUS": ACK_STATUS,
                "ACK_TIME": ACK_TIME,
            }
            event_logs_data.append(log_data)
        except Exception as e:
            print("exception reason inside code => ", e)
    try:
        response = post_data_fetch_result(
            event_logs_data,
            f"{COMMUNICATION_ADDRESS}/api/Cabinet/AMSC-CABINET-EVENT-LOG",
            post_ams_event_logs.__name__,
        )
        if response and response["status"] == 200:
            for elog in event_logs:
                elog.is_posted = 1
                session.commit()
                print(f"event {elog.id} posted successfully")
    except Exception as e:
        print("exception reason inside code => ", e)
        logger.error(e)

    print(f"{len(event_logs)} data has been posted and updated successfully.")
    mutex.release()


def post_ams_cabinet_activity_log(session):
    global CURRENT_ACTIVITY_IDS
    is_activity = (
        session.query(AMS_Activity_Progress_Status)
        .filter(AMS_Activity_Progress_Status.id == 1)
        .first()
    )
    if is_activity.is_active:
        print("execution stopped due to cabinet activities going on")
        return
    mutex.acquire()
    CABINET_ID = get_cabinet_ip(session)
    ams_cabinet_activity_logs = (
        session.query(AMS_Access_Log)
        .filter(AMS_Access_Log.is_posted == 0)
        .limit(5)
        .all()
    )
    activity_logs_data = []
    for activity_log in ams_cabinet_activity_logs:
        try:
            ACCESS_LOG_ID = activity_log.id
            SIGNINTIME = (
                str(activity_log.signInTime) if activity_log.signInTime else None
            )
            SIGNINMODE = activity_log.signInMode
            SIGNIN_FAILED = activity_log.signInFailed
            SIGNIN_SUCCEEDED = activity_log.signInSucceed
            SIGNIN_USER_ID = activity_log.signInUserId
            user = (
                session.query(AMS_Users)
                .filter(AMS_Users.id == activity_log.signInUserId)
                .first()
            )
            SIGNIN_USER_NAME = user.name if user else ""
            ACTIVITY_CODE_ENTRY_TIME = (
                str(activity_log.activityCodeEntryTime)
                if activity_log.activityCodeEntryTime
                else None
            )
            ACTIVITY_CODE = activity_log.activityCode
            DOOR_OPEN_TIME = (
                str(activity_log.doorOpenTime) if activity_log.doorOpenTime else None
            )
            KEYS_ALLOWED = (
                str(activity_log.keysAllowed) if activity_log.keysAllowed else None
            )
            KEYS_TAKEN = (
                str(activity_log.keysTaken).strip("[]")
                if activity_log.keysTaken
                else "No keys has been taken out"
            )
            KEYS_RETURNED = (
                str(activity_log.keysReturned).strip("[]")
                if activity_log.keysReturned
                else "No keys has been returned"
            )
            DOOR_CLOSED_TIME = (
                str(activity_log.doorCloseTime) if activity_log.doorCloseTime else None
            )
            EVENT_TYPE_ID = activity_log.event_type_id
            ams_cabinet_activity_log = {
                "CABINET_ID": CABINET_ID,
                "ACCESS_LOG_ID": ACCESS_LOG_ID,
                "SIGNIN_TIME": SIGNINTIME,
                "SIGNIN_MODE": SIGNINMODE,
                "SIGNIN_FAILED": SIGNIN_FAILED,
                "SIGNIN_SUCCEEDED": SIGNIN_SUCCEEDED,
                "SIGNIN_USER_ID": SIGNIN_USER_ID,
                "SIGNIN_USER_NAME": SIGNIN_USER_NAME,
                "ACTIVITY_CODE_ENTRY_TIME": ACTIVITY_CODE_ENTRY_TIME,
                "ACTIVITY_CODE": ACTIVITY_CODE,
                "DOOR_OPEN_TIME": DOOR_OPEN_TIME,
                "KEYS_ALLOWED": KEYS_ALLOWED,
                "KEYS_TAKEN": KEYS_TAKEN,
                "KEYS_RETURNED": KEYS_RETURNED,
                "DOOR_CLOSED_TIME": DOOR_CLOSED_TIME,
                "EVENT_TYPE_ID": EVENT_TYPE_ID,
            }

            CURRENT_ACTIVITY_IDS.append(activity_log.id)
            activity_logs_data.append(ams_cabinet_activity_log)

        except Exception as e:
            logger.error(e)
            print("exception reason inside code => ", e)
    try:
        response = post_data_fetch_result(
            activity_logs_data,
            f"{COMMUNICATION_ADDRESS}/api/Cabinet/AMSC-Cabinet-Activity-Log",
            post_ams_cabinet_activity_log.__name__,
        )
        print(response)
        if response and response["status"] == 200:
            for activity_log in ams_cabinet_activity_logs:
                activity_log.is_posted = 1
                session.commit()
                print(f"activity {activity_log.id} posted successfully")
            print(
                f"{len(ams_cabinet_activity_logs)} records has been posted and updated successfully."
            )
    except Exception as e:
        logger.error(e)
        print("exceptio reason inside code => ", e)
    mutex.release()


def post_ams_cabinet_keys_status(session):
    is_activity = (
        session.query(AMS_Activity_Progress_Status)
        .filter(AMS_Activity_Progress_Status.id == 1)
        .first()
    )
    if is_activity.is_active:
        print("execution stopped due to cabinet activities going on")
        return
    mutex.acquire()
    cabinet_id = get_cabinet_ip(session)
    keys_data = session.query(AMS_Keys).all()
    keys_status_data = []
    for key in keys_data:
        try:
            key_id = str(key.id)
            key_name = str(key.keyName)
            color = str(key.color)
            key_status = int(key.keyStatus)
            key_slot_no = int(key.keyPosition)
            key_strip_no = int(key.keyStrip)
            current_strip_no = key.current_pos_strip_id
            current_slot_no = key.current_pos_slot_no
            key_taken_by_uid = key.keyTakenBy if key.keyTakenBy else None
            key_taken_by_user = str(key.keyTakenByUser)
            key_taken_at = str(key.keyTakenAtTime) if key.keyTakenAtTime else ""
            ams_cabinet_key_status = {
                "CABINET_ID": cabinet_id,
                "TIMESTAMP": str(datetime.now(tz=TZ_INDIA)),
                "KEY_ID": key_id,
                "KEY_NAME": key_name,
                "COLOR": color,
                "KEY_STATUS": key_status,
                "KEY_STRIP_NO": key_strip_no,
                "KEY_SLOT_NO": key_slot_no,
                "CURRENT_STRIP_NO": current_strip_no,
                "CURRENT_SLOT_NO": current_slot_no,
                "KEY_TAKEN_BY_UID": key_taken_by_uid,
                "KEY_TAKEN_BY_NAME": key_taken_by_user,
                "KEY_TAKEN_AT": key_taken_at,
            }
            keys_status_data.append(ams_cabinet_key_status)
        except Exception as e:
            logger.error(e)
            print("exception reason inside code => ", e)
    try:
        response = post_data_fetch_result(
            keys_status_data,
            f"{COMMUNICATION_ADDRESS}/api/Cabinet/AMSC-CABINET-KEY-STATUS",
            post_ams_cabinet_keys_status.__name__,
        )
        print(response)
    except Exception as e:
        logger.error(e)
        print("exceptio reason inside code => ", e)
    mutex.release()


def get_updates(session):
    is_activity = (
        session.query(AMS_Activity_Progress_Status)
        .filter(AMS_Activity_Progress_Status.id == 1)
        .first()
    )
    if is_activity.is_active:
        print("execution stopped due to cabinet activities going on")
        return
    mutex.acquire()
    try:
        get_result = requests.get(
            url=f"{COMMUNICATION_ADDRESS}/api/Cabinet/AMSC-Track-Updates",
            params={"cabinet_id": get_cabinet_ip(session)},
            timeout=TIMEOUT,
        ).json()
    except Exception as e:
        print("exception reason inside code => ", e)
        mutex.release()
        return
    if get_result == {}:
        print("found nothing")
        mutex.release()
        return
    for table_name, records in get_result.items():
        try:

            if table_name == "AMSC_CONFIG_ACTIVITIES":
                n_records = len(records)
                print(f"{n_records} of {table_name} fetched.")
                for record in records:
                    print(record)
                    weekdays = ""
                    idx = 0
                    for k, v in json.loads(record["ACT_WEEKDAYS"]).items():
                        if v == True:
                            weekdays = weekdays + str(idx) + ","
                        idx += 1
                    weekdays = weekdays[:-1]
                    activity = (
                        session.query(AMS_Activities)
                        .filter(AMS_Activities.activityCode == record["ACT_CODE"])
                        .first()
                    )
                    if activity:
                        activity.activityName = record["ACT_NAME"]
                        activity.activityCode = record["ACT_CODE"]
                        activity.timeLimit = record["ACT_DURATION"]
                        activity.frquency = record["ACT_FREQUENCY"]

                        if record["ACT_START_TIME"]:
                            activity.timeSlotFrom = datetime.strptime(
                                record["ACT_START_TIME"][:-4], "%H:%M:%S"
                            ).time()
                        if record["ACT_END_TIME"]:
                            activity.timeSlotTo = datetime.strptime(
                                record["ACT_END_TIME"][:-4], "%H:%M:%S"
                            ).time()
                        activity.weekDays = weekdays
                        activity.keys = "".join(
                            re.sub("[^0-9 \n\.\,]", "", record["ACT_KEYS_LIST"])
                        )
                        activity.keyNames = (
                            record["KEYNAMES"] if record["KEYNAMES"] else None
                        )
                        activity.updatedAt = datetime.now(TZ_INDIA)
                        session.commit()
                    else:
                        print("activity not found!! creating a new activity...")
                        activity = AMS_Activities(
                            activityName=record["ACT_NAME"],
                            activityCode=record["ACT_CODE"],
                            timeLimit=record["ACT_DURATION"],
                            frequency=record["ACT_FREQUENCY"],
                            timeSlotFrom=datetime.strptime(
                                record["ACT_START_TIME"][:-4], "%H:%M:%S"
                            ).time(),
                            timeSlotTo=datetime.strptime(
                                record["ACT_END_TIME"][:-4], "%H:%M:%S"
                            ).time(),
                            weekDays=weekdays,
                            keys="".join(
                                re.sub("[^0-9 \n\.\,]", "", record["ACT_KEYS_LIST"])
                            ),
                            keyNames="",
                            users=record["ACT_USERS_LIST"]
                            if record["ACT_USERS_LIST"]
                            else "",
                            userNames="",
                            createdAt=datetime.now(TZ_INDIA),
                            updatedAt=datetime.now(TZ_INDIA),
                            deletedAt=None,
                        )
                        #session.add(activity)
                        #session.commit()
                    sleep(0.1)

            elif table_name == "AMSC_CONFIG_CABINET_INFO":
                n_records = len(records)
                print(f"{n_records} of {table_name} fetched.")
                for record in records:
                    print(record)
                    record["CREATEDAT"] = (
                        datetime.strptime(
                            record["CREATEDAT"][:-13], "%d-%b-%y %H.%M.%S"
                        )
                        if record["CREATEDAT"]
                        else datetime.now(TZ_INDIA)
                    )
                    record["UPDATEDAT"] = (
                        datetime.strptime(
                            record["UPDATEDAT"][:-13], "%d-%b-%y %H.%M.%S"
                        )
                        if record["UPDATEDAT"]
                        else datetime.now(TZ_INDIA)
                    )
                    print(record["CREATEDAT"])
                    cabinet = (
                        session.query(AMS_Cabinet)
                        .filter(AMS_Cabinet.ipAddress == record["IPADDRESS"])
                        .first()
                    )
                    if cabinet:
                        cabinet.cabinetName = record["CABINET_NAME"]
                        cabinet.doors = record["DOORS"]
                        cabinet.strips = record["STRIPS"]
                        cabinet.ipAddress = record["IPADDRESS"]
                        cabinet.subnetMask = record["SUBNETMASK"]
                        cabinet.geteway = record["GATEWAY"]
                        cabinet.primaryDNS = record["PRIMARYDNS"]
                        cabinet.secondaryDNS = record["SECONDARYDNS"]
                        cabinet.createdAt = record["CREATEDAT"]
                        cabinet.updatedAt = record["UPDATEDAT"]
                        if record["DOOR_OPEN"]:
                            cabinet.timeoutForDoor = record["DOOR_OPEN"]
                        if record["ALARM_TIME_OUT"]:
                            cabinet.timeoutForBattery = record["ALARM_TIME_OUT"]
                        session.commit()
                    else:
                        print("cabinet not found")
                        continue
                    sleep(0.1)

            elif table_name == "AMSC_CONFIG_RO_INFO":
                n_records = len(records)
                print(f"{n_records} of {table_name} fetched.")
                for record in records:
                    print(record)
                    record["MODIFIED_AT"] = datetime.now(TZ_INDIA)
                    ro_info = session.query(AMS_Site).first()
                    if ro_info:
                        ro_info.siteName = record["RO_NAME"]
                        ro_info.street = record["RO_STREET"]
                        ro_info.district = record["RO_DISTRICT"]
                        ro_info.city = record["RO_CITY"]
                        ro_info.state = record["RO_STATE_ID"]
                        ro_info.pinCode = record["RO_PINCODE"]
                        ro_info.contactNumber = record["RO_SUPERVISOR_MOBILE"]
                        ro_info.registrationNumber = record["RO_SITE_REGISTER_NO"]
                        ro_info.updatedAt = record["MODIFIED_AT"]
                        session.commit()
                    else:
                        print("ro info not found!! creating a new ro info instance...")
                        ro_info = AMS_Site(
                            siteName=record["RO_NAME"],
                            street=record["RO_STREET"],
                            district=record["RO_DISTRICT"],
                            city=record["RO_CITY"],
                            state=record["RO_STATE_ID"],
                            pinCode=record["RO_PINCODE"],
                            contactNumber=record["RO_SUPERVISOR_MOBILE"],
                            registrationNumber=record["RO_SITE_REGISTER_NO"],
                            createdAt=datetime.now(TZ_INDIA),
                            updatedAt=record["MODIFIED_AT"],
                            deletedAt=None,
                        )
                        session.add(ro_info)
                        session.commit()
                    sleep(0.1)

            elif table_name == "AMSC_CONFIG_USERS":
                n_records = len(records)
                print(f"{n_records} of {table_name} fetched.")
                for record in records:
                    print(record)
                    record["USER_VALIDITY_FROM"] = datetime.strptime(
                        record["USER_VALIDITY_FROM"][:10], "%Y-%m-%d"
                    )
                    record["USER_VALIDITY_TO"] = datetime.strptime(
                        record["USER_VALIDITY_TO"][:10], "%Y-%m-%d"
                    )
                    user = (
                        session.query(AMS_Users)
                        .filter(AMS_Users.name == record["USER_NAME"])
                        .first()
                    )
                    if user:
                        user.name = record["USER_NAME"]
                        user.email = record["USER_EMAIL"]
                        user.mobileNumber = record["USER_MOBILE"]
                        user.validityFrom = record["USER_VALIDITY_FROM"]
                        user.validityTo = record["USER_VALIDITY_TO"]
                        user.pinCode = record["USER_AMS_PIN"]
                        user.roleId = record["USER_ROLE_ID"]
                        user.isActive = (
                            record["USER_IS_ACTIVE"] if record["USER_IS_ACTIVE"] else 1
                        )
                        user.cabinetId = get_cabinet_id(session)
                        user.cardNo = (
                            record["USER_CARD_NO"] if record["USER_CARD_NO"] else None
                        )
                        user.updatedAt = datetime.now(TZ_INDIA)
                        session.commit()
                    else:
                        print("user not found!! creating a new user instance....")
                        user = AMS_Users(
                            name=record["USER_NAME"],
                            email=record["USER_EMAIL"],
                            mobileNumber=record["USER_MOBILE"],
                            validityFrom=record["USER_VALIDITY_FROM"],
                            validityTo=record["USER_VALIDITY_TO"],
                            pinCode=record["USER_AMS_PIN"],
                            roleId=record["USER_ROLE_ID"],
                            lastLoginDate=None,
                            isActive=record["USER_IS_ACTIVE"]
                            if record["USER_IS_ACTIVE"]
                            else 0,
                            isActiveInt=int(record["USER_IS_ACTIVE"])
                            if record["USER_IS_ACTIVE"]
                            else 0,
                            cabinetId=get_cabinet_id(session),
                            createdAt=datetime.now(TZ_INDIA),
                            updatedAt=datetime.now(TZ_INDIA),
                            deletedAt=None,
                            cardNo=record["USER_CARD_NO"]
                            if record["USER_CARD_NO"]
                            else None,
                            fpTemplate=None,
                        )
                        #session.add(user)
                        #session.commit()
                    sleep(0.1)

            elif table_name == "AMSC_EVENTTYPES":
                n_records = len(records)
                print(f"{n_records} of {table_name} fetched.")
                for record in records:
                    print(record)
                    event = (
                        session.query(AMS_Events)
                        .filter(AMS_Events.eventName == record["EVENT_NAME"])
                        .first()
                    )
                    if event:
                        event.eventName = record["EVENT_NAME"]
                        event.updatedAt = datetime.now(tz_IN)
                        session.commit()
                    else:
                        print("event not found! creating a new event instance...")
                        event = AMS_Events(
                            eventName=record["EVENT_NAME"],
                            createdAt=datetime.now(tz_IN),
                            updatedAt=datetime.now(tz_IN),
                        )
                        session.add(event)
                        session.commit()
                    sleep(0.1)

            elif table_name == "AMSC_CONFIG_KEYS":
                n_records = len(records)
                print(f"{n_records} of {table_name} fetched.")
                for record in records:
                    record["KEY_ID"] = int(record["KEY_ID"])
                    print(record)
                    key = (
                        session.query(AMS_Keys)
                        .filter(AMS_Keys.keyName == record["KEY_NAME"])
                        .first()
                    )
                    if key:
                        key.keyName = record["KEY_NAME"]
                        key.description = record["KEY_DESCRIPTION"]
                        key.color = record["KEY_COLOR"]
                        key.keyAtDoor = record["KEY_DOOR_NO"]
                        key.keyStrip = record["KEY_STRIP_NO"]
                        key.keyLocation = record["KEY_SLOT_NO"]
                        key.updatedAt = datetime.now(TZ_INDIA)
                        session.commit()
                    else:
                        print("key not found! creating new instance of the key...")
                        ams_key = AMS_Keys(
                            keyName=record["KEY_NAME"],
                            description=record["KEY_DESCRIPTION"],
                            color=record["KEY_COLOR"],
                            keyAtDoor=record["KEY_DOOR_NO"],
                            keyStrip=record["KEY_STRIP_NO"],
                            keyPosition=None,
                            keyLocation=record["KEY_SLOT_NO"],
                            keyStatus=0,
                            keyTakenBy=None,
                            current_pos_door_id=record["KEY_DOOR_NO"],
                            current_pos_strip_id=record["KEY_STRIP_NO"],
                            current_pos_slot_no=record["KEY_SLOT_NO"],
                            keyTakenAtTime=None,
                            peg_id=None,
                            cabinetId=get_cabinet_id(session),
                            keyTakenByUser=None,
                            createdAt=datetime.now(TZ_INDIA),
                            updatedAt=datetime.now(TZ_INDIA),
                            deletedAt=None,
                        )
                        session.add(ams_key)
                        session.commit()
                    sleep(0.1)

        except Exception as e:
            print(f"exception reason inside code => ", e)
            session.rollback()
            continue
    mutex.release()


def download_firmware_udpate_file(file_location):
    url = f"{COMMUNICATION_ADDRESS}/api/Portal_Management/get-zip-file"
    filename = None
    file_path = None
    try:
        filename = file_location.split("/")[-1]
    except Exception as e:
        logger.error(e)
        print(e)
    if filename == "" or filename is None:
        filename = "Firmware-Update.zip"
    file_path = f"/home/{filename}"
    try:
        response = requests.get(
            url,
            data={"file_path": file_location},
            timeout=10,
            stream=True,
            allow_redirects=True,
        )
        with open(file_path, "wb") as output_file:
            output_file.write(response.content)
        print("Downloading Completed")
    except Exception as e:
        print(e)
    return filename, file_path


# def setDateTimeFromServer(session):
#     is_activity = (
#         session.query(AMS_Activity_Progress_Status)
#         .filter(AMS_Activity_Progress_Status.id == 1)
#         .first()
#     )
#     if is_activity.is_active:
#         print("execution stopped due to cabinet activities going on")
#         return
#     mutex.acquire()
#     try:
#         get_result = requests.get(
#             url=f"{COMMUNICATION_ADDRESS}/api/Cabinet/AmsGetTimestamp",
#             #url="http://192.168.1.115:8001/api/Cabinet/AmsGetTimestamp",
#             # params={"cabinet_id": get_cabinet_ip(session)},
#             timeout=TIMEOUT,
#         ).json()
#     except Exception as e:
#         print("** set Date Time From Server::exception reason inside code => ", e)
#         mutex.release()
#         return
#     if get_result == {}:
#         print("** set DateTime From Server::blank response from server")
#         mutex.release()
#         return
#     elif get_result["status"] == 200:
#         try:
#             date_str = get_result["timestamp"]  # server sends date in format -> 'YYYY-MM-DD HH:mm:ss'
#             os.system('timedatectl set-ntp false')
#             sleep(2)
#             os.system('timedatectl set-time ' + "'" + date_str + "'")
#             print("** set Date Time From Server:: date & time synced with server successfully")
#         except Exception as e:
#             print(e)
#
#         mutex.release()
#         return


def check_for_updates(session, lib_display):
    print("%" * 200)
    print("inside check for updates")
    print("%" * 200)
    is_activity = (
        session.query(AMS_Activity_Progress_Status)
        .filter(AMS_Activity_Progress_Status.id == 1)
        .first()
    )
    if is_activity.is_active:
        print("execution stopped due to cabinet activities going on")
        return
    mutex.acquire()
    cabinet_id = get_cabinet_ip(session)
    current_version = 1.0
    data = {"CABINET_ID": cabinet_id, "CURRENT_VERSION": current_version}
    cnt = 1
    while True and cnt <= 5:
        try:
            response = requests.get(
                url=f"{COMMUNICATION_ADDRESS}/api/Cabinet/AMSC-Check-Updates",
                params=data,
                timeout=TIMEOUT,
            ).json()
            break
        except Exception as e:
            print(f"server down: {e}")
            cnt += 1
            sleep(10)
    if cnt == 5:
        logger.error("threshold reached and server didn't respond!")
        print("threshold reached and server didn't respond!")
        mutex.release()
        return None
    try:
        print(response)
        if response["status"] == 200:
            if response["update_available"] == 1:

                file_location = response["file_location"]

                if os.path.exists("/home/Firmware-Update/"):
                    os.system("rm -rf /home/Firmware-Update/")

                if os.path.exists("/home/Firmware-Update.zip"):
                    os.system("rm /home/Firmware-Update.zip")

                lib_display.displayString("Cabinet Updating".encode("utf-8"), 1)
                lib_display.displayString("Please Wait ....".encode("utf-8"), 2)

                filename, file_path = download_firmware_udpate_file(file_location)

                if filename in os.listdir("/home/"):
                    os.system(f"unzip {file_path} -d /home/")
                    sleep(1)
                    if os.path.exists("/home/Firmware-Update/"):
                        try:
                            file_folder = file_path[:-4] + "/"
                            os.chdir(file_folder)
                            if "updates.py" in os.listdir(os.getcwd()):
                                try:
                                    return_val = os.system(f"python3 updates.py")
                                    if return_val != 0:
                                        raise Exception()
                                except Exception as e:
                                    print("exception occured while updating cabinet")
                                    lib_display.displayClear()
                                    lib_Buzzer.setBuzzerOn()
                                    lib_display.displayString(
                                        "Exception Occured".encode("utf-8"), 1
                                    )
                                    lib_display.displayString(
                                        "Contact CSI Team".encode("utf-8"), 2
                                    )
                                    sleep(10)
                                    lib_Buzzer.setBuzzerOff()
                                    mutex.release()
                                    return
                                success_data = {
                                    "CABINET_ID": cabinet_id,
                                }
                                response2 = post_data_fetch_result(
                                    success_data,
                                    f"{COMMUNICATION_ADDRESS}/api/Cabinet/AMSC-Submit-Update-Status",
                                    "successful_software_update",
                                )
                                if response2["status"] == 200:
                                    print("updation details pushed successfully")
                                    os.system(f"rm {file_path}")
                                    os.system(f"rm -rf {file_folder}")
                                    os.system("reboot")
                                else:
                                    print(
                                        "some exception occured while pushing data for new version update"
                                    )
                            else:
                                print("updates.py file not found")
                        except Exception as e:
                            print("exception occured while updating the file")
                            print(e)
                    else:
                        print("updated package not found!")
                else:
                    print("zip package not found!!")
            else:
                print("software is up to date")
            lib_display.displayClear()
    except Exception as e:
        print(e)
    mutex.release()


def reset_activity_progress(session):
    print("inside reset_activity_progress")
    is_activity = (
        session.query(AMS_Activity_Progress_Status)
        .filter(AMS_Activity_Progress_Status.id == 1)
        .first()
    )
    if is_activity.is_active:
        is_activity.is_active = 0
        session.commit()
        print("activity progress status got reset!")


def check_file_size():
    file_path = LOGFILE_PATH
    if os.path.exists(file_path):
        file_size = os.path.getsize(file_path)
        curr_hr = int(str(datetime.now().time())[:2])
        if file_size >= 5000000 and curr_hr >= 3 and curr_hr <= 4:
            print("apicalls file got reinitialized")
            logger.info("apicalls file got reinitialized")
            os.system(f"rm {LOGFILE_PATH}")
            os.system("reboot")


if __name__ == "__main__":

    logging.basicConfig(
        filename=LOGFILE_PATH,
        format="%(asctime)s %(message)s",
        filemode="a",
    )
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    lib_KeyboxLock = ctypes.CDLL("libKeyboxLock.so")
    lib_KeyboxLock.getDoorSensorStatus1.argtypes = []
    lib_KeyboxLock.setKeyBoxLock.argtypes = [ctypes.c_int]
    lib_KeyboxLock.getDoorSensorStatus1.argtypes = []

    lib_Buzzer = ctypes.CDLL("libBuzzer.so")
    lib_Buzzer.setBuzzerOn.argtypes = []
    lib_Buzzer.setBuzzerOff.argtypes = []

    lib_display = ctypes.CDLL("libDisplay.so")
    lib_display.displayDefaultLoginMessage.argtypes = []
    lib_display.displayStringWithPosition.argtypes = [
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_int,
    ]
    lib_display.displayString.argtypes = [ctypes.c_char_p, ctypes.c_int]
    lib_display.displayClear.argtypes = []
    lib_display.displayInit.argtypes = []
    lib_display.displayClose.argtypes = []
    lib_display.displayInit()

    try:
        engine = create_engine(
            SQLALCHEMY_DATABASE_URI, connect_args={"check_same_thread": False}
        )
        Session = sessionmaker()
        Session.configure(bind=engine, autocommit=False, autoflush=False)
        session = Session()
    except Exception as e:
        logger.error(e)
        print(e)
    cabinet = session.query(AMS_Cabinet).first()

    schedule.every(2).minutes.do(
        post_cabinet_status, session, lib_KeyboxLock
    )
    schedule.every(1).minutes.do(post_ams_cabinet_keys_status, session)
    schedule.every(70).seconds.do(post_ams_cabinet_activity_log, session)
    schedule.every(80).seconds.do(post_ams_event_logs, session)
    schedule.every(30).minutes.do(post_ams_users, session)
    #schedule.every(5).minutes.do(get_updates, session)
    schedule.every(3).hours.do(check_for_updates, session, lib_display)
    schedule.every(10).minutes.do(reset_activity_progress, session)
    schedule.every(15).minutes.do(check_file_size)

    while True:
        try:
            schedule.run_pending()
            sleep(1)
        except Exception as e:
            sleep(5)
            print(e)
            logger.error(e)
