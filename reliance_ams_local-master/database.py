from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


try:
    engine = create_engine("sqlite:////home/ams-core/csiams.dev.sqlite", echo=False)
    Session = sessionmaker()
    Session.configure(bind=engine)
    session = Session()
    Base = declarative_base()
except Exception as e:
    print(e)
    print("error occured during conneting to sqlite database!")
