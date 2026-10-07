import os

from sqlalchemy import Column, Float, Integer, String, Text, create_engine
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


class FallEvent(Base):
    __tablename__ = "fall_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Integer, index=True)
    decision = Column(String(32), nullable=False)
    smv_peak_g = Column(Float)
    reasons = Column(Text)


class VitalSession(Base):
    __tablename__ = "vital_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Integer, index=True)
    decision = Column(String(32), nullable=False)
    subset_total = Column(Integer)
    max_component = Column(Integer)
    reasons = Column(Text)


class AlertRecord(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Integer, index=True)
    alert_level = Column(String(32), nullable=False)
    fall_decision = Column(String(32))
    vitals_decision = Column(String(32))
    algorithm_version = Column(String(64))
    reasons = Column(Text)
    ack_label = Column(String(32))


Base.metadata.create_all(bind=engine)
