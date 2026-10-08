import os

from sqlalchemy import (
    Column,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from common.config import load_gateway_env, sqlite_path, sqlite_url

load_gateway_env()

db_file = sqlite_path()
os.makedirs(db_file.parent, exist_ok=True)

DATABASE_URL = sqlite_url()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


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


class RawEvent(Base):
    __tablename__ = "raw_events"
    __table_args__ = (UniqueConstraint("device_id", "seq", name="uq_device_seq"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), index=True, nullable=False)
    seq = Column(Integer, nullable=False)
    kind = Column(String(32), nullable=False)
    ts_ms = Column(Integer, nullable=False)
    payload = Column(Text, nullable=False)


class FallEvent(Base):
    __tablename__ = "fall_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Integer, index=True)
    device_id = Column(String(64), index=True)
    decision = Column(String(32), nullable=False)
    l_fall = Column(Integer)
    smv_peak_g = Column(Float)
    reasons = Column(Text)


class VitalSession(Base):
    __tablename__ = "vital_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Integer, index=True)
    device_id = Column(String(64), index=True)
    session_id = Column(String(64))
    decision = Column(String(32), nullable=False)
    subset_total = Column(Integer)
    max_component = Column(Integer)
    completeness = Column(Float)
    reasons = Column(Text)


class AlertRecord(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Integer, index=True)
    device_id = Column(String(64), index=True)
    alert_level = Column(String(32), nullable=False)
    l = Column(Integer)
    state = Column(String(32), default="open")
    fall_decision = Column(String(32))
    vitals_decision = Column(String(32))
    device_status = Column(String(32))
    algorithm_version = Column(String(64))
    reasons = Column(Text)
    ack_label = Column(String(32))


class ManualVital(Base):
    __tablename__ = "manual_vitals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), index=True, nullable=False)
    name = Column(String(32), nullable=False)
    value = Column(String(32), nullable=False)
    valid_until = Column(Integer)
    entered_at = Column(Integer)


Base.metadata.create_all(bind=engine)
