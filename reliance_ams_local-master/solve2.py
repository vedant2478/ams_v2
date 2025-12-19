from sqlalchemy import Column, Integer, String, ForeignKey, Table, create_engine, or_, and_, BINARY, func
from sqlalchemy.orm import relationship, backref, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.expression import distinct, intersect_all, null, true
from sqlalchemy.sql.functions import concat, now, user
from sqlalchemy.sql.sqltypes import DATETIME, INTEGER, SMALLINT, DateTime, Time
from datetime import date, datetime, timedelta
import pytz

tz_IN = pytz.timezone('Asia/Kolkata')

from model import AMS_Users

engine = create_engine('sqlite:////home/ams-core/csiams.dev.sqlite')
Session = sessionmaker()
Session.configure(bind=engine)
session = Session()

flag = 0

users = session.query(AMS_Users).all()
for user in users:
    user.validityTo = datetime(2027, 11, 1, tzinfo=tz_IN)
    session.commit()
    
print(f"all users updated successfully and flag = {flag}!")