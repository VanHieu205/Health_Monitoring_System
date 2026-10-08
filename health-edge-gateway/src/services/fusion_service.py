"""fusion + local_alert: L = max(L_news, L_fall, L_trend); hysteresis; lifecycle."""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC))

from algorithms.device_status import DeviceStatus
from algorithms.fusion import DecisionFusion
from algorithms.news2 import ALGORITHM_VERSION
from common.config import load_gateway_env
from common.topics import (
    DEVICE_STATUS,
    FALL_DECISION,
    LOCAL_ALARM,
    NEWS2_DECISION,
    NURSE_ACK,
    NURSE_ALERT,
    TREND_DECISION,
    WATCH_HEARTBEAT,
)
from local_storage.db_models import AlertRecord, SessionLocal
from services.bus import publish_json
from services.mqtt_loop import device_id_from_topic, run_subscriber

load_gateway_env()
LOGGER = logging.getLogger("fusion")

_latest: dict[str, dict[str, dict]] = {}
_hyst: dict[str, tuple[int, int]] = {}
_open: dict[str, int] = {}
_fusion = DecisionFusion()


def _fuse(device_id: str) -> None:
    bag = _latest.setdefault(device_id, {})
    news = bag.get("news2", {})
    fall = bag.get("fall", {})
    trend = bag.get("trend", {})
    device = bag.get("device", {})
    ack = bag.get("ack", {})
    prev, consec = _hyst.get(device_id, (None, 0))
    fused = _fusion.fuse(
        l_news=int(news.get("l_news") or 0),
        l_fall=int(fall.get("l_fall") or 0),
        l_trend=int(trend.get("l_trend") or 0),
        s=int(news.get("s") or 0),
        s_max=int(news.get("s_max") or 0),
        completeness=float(news.get("completeness") or 0.0),
        n_valid=int(news.get("n_valid") or (7 - len(news.get("missing") or []))),
        missing=tuple(news.get("missing") or ()),
        needs_confirmation=bool(news.get("needs_confirmation")),
        device_status=device.get("status", DeviceStatus.DEVICE_OK.value),
        previous_l=prev,
        consecutive_lower=consec,
        nurse_ack=bool(ack.get("ack")),
        news_reasons=tuple(news.get("reasons") or ()),
        fall_reasons=tuple(fall.get("reasons") or ()),
        trend_reasons=tuple(trend.get("reasons") or ()),
        fall_decision=str(fall.get("decision") or "none"),
        ppg_valid=bool(news.get("completeness", 0) > 0),
    )
    if prev is not None and fused.l < prev:
        _hyst[device_id] = (fused.l, 0)
    elif prev is not None and fused.l == prev:
        _hyst[device_id] = (fused.l, 0)
    elif fused.hysteresis_held:
        _hyst[device_id] = (prev, consec + 1)
    else:
        _hyst[device_id] = (fused.l, 0)

    now = int(time.time())
    open_id = _open.get(device_id)
    db = SessionLocal()
    if fused.l == 0:
        if open_id is not None:
            row = db.query(AlertRecord).filter(AlertRecord.id == open_id).first()
            if row is not None:
                row.state = "resolved"
            _open.pop(device_id, None)
            db.commit()
        db.close()
        payload = _payload(device_id, fused, now, "resolved" if open_id else "ok")
        publish_json(NURSE_ALERT, payload)
        LOGGER.info("%s", json.dumps(payload, default=str))
        return

    if open_id is not None:
        row = db.query(AlertRecord).filter(AlertRecord.id == open_id).first()
        if row is not None and row.l == fused.l and row.state == "open":
            row.reasons = json.dumps(fused.reasons)
            db.commit()
            db.close()
            return
    row = AlertRecord(
        timestamp=now,
        device_id=device_id,
        alert_level=fused.alert_level,
        l=fused.l,
        state="open",
        fall_decision=fused.fall_decision,
        vitals_decision=news.get("decision"),
        device_status=fused.device_status,
        algorithm_version=ALGORITHM_VERSION,
        reasons=json.dumps(fused.reasons),
    )
    db.add(row)
    db.commit()
    _open[device_id] = row.id
    db.close()
    payload = _payload(device_id, fused, now, "open")
    publish_json(NURSE_ALERT, payload)
    if fused.l >= 2:
        publish_json(LOCAL_ALARM, payload)
    LOGGER.info("%s", json.dumps(payload, default=str))


def _payload(device_id: str, fused, now: int, state: str) -> dict:
    return {
        "device_id": device_id,
        "l": fused.l,
        "alert_level": fused.alert_level,
        "alert_source": fused.alert_source,
        "l_news": fused.l_news,
        "l_fall": fused.l_fall,
        "l_trend": fused.l_trend,
        "s": fused.s,
        "s_max": fused.s_max,
        "completeness": fused.completeness,
        "missing": fused.missing,
        "needs_confirmation": fused.needs_confirmation,
        "device_status": fused.device_status,
        "fall_decision": fused.fall_decision,
        "state": state,
        "reasons": fused.reasons,
        "algorithm_version": fused.algorithm_version,
        "timestamp": now,
    }


def handle(topic: str, payload: dict) -> None:
    device_id = str(payload.get("device_id") or device_id_from_topic(topic))
    if not device_id:
        return
    if topic == NEWS2_DECISION or topic.endswith("/news2/decision"):
        _latest.setdefault(device_id, {})["news2"] = payload
    elif topic == FALL_DECISION or topic.endswith("/fall/decision"):
        _latest.setdefault(device_id, {})["fall"] = payload
    elif topic == TREND_DECISION or topic.endswith("/trend/decision"):
        _latest.setdefault(device_id, {})["trend"] = payload
    elif topic == NURSE_ACK or topic.endswith("/ack"):
        _latest.setdefault(device_id, {})["ack"] = {"ack": True, **payload}
        db = SessionLocal()
        open_id = _open.get(device_id)
        if open_id is not None:
            row = db.query(AlertRecord).filter(AlertRecord.id == open_id).first()
            if row is not None:
                row.state = "acknowledged"
                row.ack_label = str(payload.get("label") or "ack")
                db.commit()
        db.close()
    elif topic == DEVICE_STATUS or "heartbeat" in topic:
        status = payload.get("status")
        if "heartbeat" in topic:
            from algorithms.device_status import classify_device

            age = 0.0
            status = classify_device(
                heartbeat_age_s=age,
                battery_percent=payload.get("battery"),
                worn=payload.get("worn", True),
            ).status.value
        _latest.setdefault(device_id, {})["device"] = {"status": status}
        publish_json(DEVICE_STATUS, {"device_id": device_id, "status": status})
    _fuse(device_id)


def main() -> None:
    run_subscriber(
        "fusion",
        [NEWS2_DECISION, FALL_DECISION, TREND_DECISION, NURSE_ACK, WATCH_HEARTBEAT],
        handle,
    )


if __name__ == "__main__":
    main()
