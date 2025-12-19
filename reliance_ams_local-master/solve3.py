from sqlalchemy import Column, Integer, String, DateTime, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import pytz

Base = declarative_base()

tz_IN = pytz.timezone('Asia/Kolkata')

class AMS_Users(Base):
    __tablename__ = 'ams_users'
    id = Column(Integer, primary_key=True)
    name = Column(String)

class EventType(Base):
    __tablename__ = 'event_types'
    eventId = Column(Integer, primary_key=True)
    eventDescription = Column(String)
    eventMessage = Column(String)
    eventType = Column(Integer)

class Events(Base):
    __tablename__ = 'events'
    Id = Column(Integer, primary_key=True)
    eventName = Column(String)
    createdAt = Column(DateTime)
    updatedAt = Column(DateTime)
    deletedAt = Column(DateTime)

# Database connection
engine = create_engine('sqlite:////home/ams-core/csiams.dev.sqlite')
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

flag = 0

# ✅ Only new Event Types (keeping 15–18 as they are)
event_types_new = [
    {"eventId": 19, "eventDescription": "Key Overdue", "eventMessage": "Key Overdue", "eventType": 2},
    {"eventId": 20, "eventDescription": "Date Set", "eventMessage": "Date Set", "eventType": 3},
    {"eventId": 28, "eventDescription": "IP change initialised", "eventMessage": "IP change initialised", "eventType": 3},
    {"eventId": 29, "eventDescription": "IP change failed", "eventMessage": "IP change failed", "eventType": 3},
    {"eventId": 31, "eventDescription": "Overdue Key Returned", "eventMessage": "Overdue Key Returned", "eventType": 2},
    {"eventId": 32, "eventDescription": "Bio Registration Done", "eventMessage": "Bio Registration Done", "eventType": 3},
    {"eventId": 33, "eventDescription": "Bio Registration Failed", "eventMessage": "Bio Registration Failed", "eventType": 3},
]

# Insert new EventTypes if not present
for event_data in event_types_new:
    if not session.query(EventType).filter_by(eventId=event_data["eventId"]).first():
        new_event_type = EventType(**event_data)
        session.add(new_event_type)
        flag += 1

session.commit()
print(f"New EventTypes added successfully! Total newly inserted = {flag}")

# ✅ Events for new EventTypes
events_data_new = [
    {"Id": e["eventId"], "eventName": e["eventDescription"],
     "createdAt": datetime.now(tz_IN), "updatedAt": datetime.now(tz_IN), "deletedAt": None}
    for e in event_types_new
]

for event_data in events_data_new:
    if not session.query(Events).filter_by(Id=event_data["Id"]).first():
        new_event = Events(**event_data)
        session.add(new_event)
        flag += 1

session.commit()
print(f"New Events added successfully! Total newly inserted = {flag}")

# Mapping of eventId to new eventType values
update_map = {
    1: 3, 2: 3, 3: 3, 4: 1,
    5: 3, 6: 3, 7: 3, 8: 1,
    9: 3, 10: 2, 11: 3, 12: 1,
    13: 3, 14: 2, 15: 3, 16: 3,
    17: 3, 18: 3
}

# Perform the updates
for eventId, new_type in update_map.items():
    row = session.query(EventType).filter_by(eventId=eventId).first()
    if row:
        row.eventType = new_type

session.commit()
print("EventType column updated successfully for eventId 1–18")

