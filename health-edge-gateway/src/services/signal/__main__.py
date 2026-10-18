"""Estimate HR/SpO2/RR/temp from watch session features and apply PPG IQR gate."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC))

from domain.vitals_estimate import hr_from_ibi, rr_from_modulations, spo2_from_r
from runtime.config import load_gateway_env
from contracts.topics import SIGNAL, WATCH_PPG, WATCH_TEMP
from persistence.db_models import SessionLocal, VitalSession
from services.branches.snn import read as read_motion
from services.branches.sqi import read as read_sqi
from runtime.bus import publish_json
from runtime.mqtt import device_id_from_topic, run_subscriber

load_gateway_env()
LOGGER = logging.getLogger("signal_proc")

A = float(os.getenv("SPO2_CAL_A", "0"))
B = float(os.getenv("SPO2_CAL_B", "-15"))
C = float(os.getenv("SPO2_CAL_C", "110"))
MAX_IQR_HR = float(os.getenv("PPG_MAX_IQR_HR_BPM", "10"))
MAX_IQR_SPO2 = float(os.getenv("PPG_MAX_IQR_SPO2_PCT", "2"))


def handle(topic: str, payload: dict) -> None:
    device_id = payload.get("device_id") or device_id_from_topic(topic)
    kind = topic.rsplit("/", 1)[-1]
    now = int(payload.get("ts_ms") or time.time() * 1000)
    if kind == "temp":
        out = {
            "device_id": device_id,
            "kind": "temp",
            "temperature_c": payload.get("temperature_c") or payload.get("mean_c"),
            "std_c": payload.get("std_c"),
            "gate_ok": float(payload.get("std_c") or 0) <= 0.3,
            "source": "estimated",
            "ts_ms": now,
        }
        publish_json(SIGNAL, out)
        return

    ibi = payload.get("ibi_s") or []
    hr = payload.get("median_hr")
    if hr is None and ibi:
        hr = hr_from_ibi(ibi)
    r_vals = payload.get("r_values") or []
    spo2 = payload.get("median_spo2")
    if spo2 is None and r_vals:
        spo2 = spo2_from_r(r_vals, a=A, b=B, c=C)
    rr = payload.get("rr")
    if rr is None and all(k in payload for k in ("f_riiv", "f_riav", "f_rifv")):
        rr = rr_from_modulations(payload["f_riiv"], payload["f_riav"], payload["f_rifv"])
    iqr_hr = payload.get("iqr_hr")
    iqr_spo2 = payload.get("iqr_spo2")
    n_beats = payload.get("n_valid_beats", len(ibi) if ibi else payload.get("n_valid_hr", 0))
    motion = read_motion(payload)
    motion_ok = payload.get("motion_ok")
    if motion_ok is None:
        motion_ok = (not motion.available) or motion.label in {"rest", "sit_stand"}
    sqi = read_sqi(payload)
    reasons = []
    if n_beats is not None and int(n_beats) < 20:
        reasons.append("few_beats")
    if iqr_hr is not None and float(iqr_hr) > MAX_IQR_HR:
        reasons.append("iqr_hr")
    if iqr_spo2 is not None and float(iqr_spo2) > MAX_IQR_SPO2:
        reasons.append("iqr_spo2")
    if not motion_ok:
        reasons.append("motion")
    if sqi.available and sqi.label == "fail":
        reasons.append("sqi_model")
    gate_ok = not reasons and hr is not None and spo2 is not None
    out = {
        "device_id": device_id,
        "kind": "ppg",
        "session_id": payload.get("session_id"),
        "hr": hr,
        "spo2": spo2,
        "rr": rr,
        "rr_source": "estimated" if rr is not None else "missing",
        "iqr_hr": iqr_hr,
        "iqr_spo2": iqr_spo2,
        "gate_ok": gate_ok,
        "reasons": reasons,
        "source": "measured",
        "ts_ms": now,
    }
    db = SessionLocal()
    db.add(
        VitalSession(
            timestamp=now // 1000,
            device_id=device_id,
            session_id=str(payload.get("session_id") or ""),
            decision="ppg_ok" if gate_ok else "ppg_fail",
            reasons=json.dumps(reasons),
        )
    )
    db.commit()
    db.close()
    publish_json(SIGNAL, out)
    LOGGER.info("%s", json.dumps(out, default=str))


def main() -> None:
    run_subscriber("signal_proc", [WATCH_PPG, WATCH_TEMP], handle)


if __name__ == "__main__":
    main()
