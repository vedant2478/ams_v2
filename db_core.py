from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URI = (
    "sqlite:////home/rock/Desktop/ams_v2/csiams.dev.sqlite"
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URI,
    echo=False,
    connect_args={"check_same_thread": False}, 
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)
