import os

from sqlalchemy import Column, Integer, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from common.config import load_gateway_env, sqlite_path, sqlite_url

load_gateway_env()

db_file = sqlite_path()
os.makedirs(db_file.parent, exist_ok=True)

DATABASE_URL = sqlite_url()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class SensorRecord(Base):
    __tablename__ = "sensor_raw_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Integer, index=True)
    hr = Column(Integer)
    spo2 = Column(Integer)
    ax = Column(Integer)
    ay = Column(Integer)
    az = Column(Integer)
    event_flag = Column(Integer)
    battery = Column(Integer)


Base.metadata.create_all(bind=engine)
