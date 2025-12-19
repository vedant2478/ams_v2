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

engine = create_engine('sqlite:////home/ams-core/csiams.dev.sqlite')
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

flag = 0

event_types = [
    {"eventId": 15, "eventDescription": "Pegs Registration Done", "eventMessage": "Pegs Reg Done", "eventType": 1},
    {"eventId": 16, "eventDescription": "Pegs Registration Failed", "eventMessage": "Pegs Reg Failed", "eventType": 2},
    {"eventId": 17, "eventDescription": "Card Registration Done", "eventMessage": "Card Reg Done", "eventType": 1},
    {"eventId": 18, "eventDescription": "Card Registration Failed", "eventMessage": "Card Reg Failed", "eventType": 2}
]

for event_data in event_types:
    new_event = EventType(
        eventId=event_data["eventId"],
        eventDescription=event_data["eventDescription"],
        eventMessage=event_data["eventMessage"],
        eventType=event_data["eventType"]
    )
    session.add(new_event)

session.commit()

print(f"All Event_types added successfully and flag = {flag}!")

session = Session()

events_data = [
    {"Id": 15, "eventName": "Pegs Registration Done", "createdAt": datetime.now(tz_IN), "updatedAt": datetime.now(tz_IN), "deletedAt": None},
    {"Id": 16, "eventName": "Pegs Registration Failed", "createdAt": datetime.now(tz_IN), "updatedAt": datetime.now(tz_IN), "deletedAt": None},
    {"Id": 17, "eventName": "Card Registration Done", "createdAt": datetime.now(tz_IN), "updatedAt": datetime.now(tz_IN), "deletedAt": None},
    {"Id": 18, "eventName": "Card Registration Failed", "createdAt" :datetime.now(tz_IN), "updatedAt": datetime.now(tz_IN), "deletedAt": None},
]

for event_data in events_data:
    new_event = Events(
        Id=event_data["Id"],
        eventName=event_data["eventName"],
        createdAt=event_data["createdAt"],
        updatedAt=event_data["updatedAt"],
        deletedAt=event_data["deletedAt"]
    )
    session.add(new_event)

session.commit()

print(f"All Events added successfully and flag = {flag}!")
