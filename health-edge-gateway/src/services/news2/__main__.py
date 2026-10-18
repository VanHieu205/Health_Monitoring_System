"""branch_news2: latest gated vitals + nurse entries → L_news."""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC))

from domain.news2 import ALGORITHM_VERSION, manual_ttl_hours
from domain.news2_branch import News2Branch, News2Inputs, VitalObservation, VitalSource
from runtime.config import load_gateway_env
from contracts.topics import MANUAL_INPUT, NEWS2_DECISION, SIGNAL
from persistence.db_models import ManualVital, SessionLocal
from runtime.bus import publish_json
from runtime.mqtt import run_subscriber

load_gateway_env()
LOGGER = logging.getLogger("news2")

_auto: dict[str, dict] = {}
_branch = News2Branch()


def _obs(payload: dict | None, key: str, source: VitalSource) -> VitalObservation:
    if not payload or payload.get(key) is None:
        return VitalObservation()
    gate = bool(payload.get("gate_ok", True))
    ts = payload.get("ts_ms")
    until = None if ts is None else int(ts) / 1000.0 + 15 * 60
    return VitalObservation(
        source=source,
        value=payload[key],
        gate_ok=gate,
        measured_at=None if ts is None else int(ts) / 1000.0,
        valid_until=until,
    )


def _manual(device_id: str, name: str, now: float) -> VitalObservation:
    db = SessionLocal()
    row = (
        db.query(ManualVital)
        .filter(ManualVital.device_id == device_id, ManualVital.name == name)
        .order_by(ManualVital.id.desc())
        .first()
    )
    db.close()
    if row is None:
        return VitalObservation()
    value: float | str | bool = row.value
    if name == "on_oxygen":
        value = row.value in {"1", "true", "True"}
    elif name != "consciousness":
        value = float(row.value)
    until = None if row.valid_until is None else float(row.valid_until)
    return VitalObservation(
        source=VitalSource.MANUAL,
        value=value,
        gate_ok=True,
        valid_until=until,
    )


def _publish(device_id: str) -> None:
    now = time.time()
    auto = _auto.get(device_id, {})
    ppg = auto.get("ppg")
    temp = auto.get("temp")
    man_rr = _manual(device_id, "rr", now)
    man_temp = _manual(device_id, "temperature", now)
    man_scale2 = _manual(device_id, "scale2", now)
    scale2 = man_scale2.usable(now) and str(man_scale2.value).lower() in {"1", "true", "yes"}
    inputs = News2Inputs(
        pulse=_obs(ppg, "hr", VitalSource.MEASURED),
        spo2=_obs(ppg, "spo2", VitalSource.MEASURED),
        rr=man_rr if man_rr.usable(now) else _obs(ppg, "rr", VitalSource.ESTIMATED),
        temperature=man_temp if man_temp.usable(now) else _obs(temp, "temperature_c", VitalSource.ESTIMATED),
        sbp=_manual(device_id, "sbp", now),
        consciousness=_manual(device_id, "consciousness", now),
        on_oxygen=_manual(device_id, "on_oxygen", now),
        scale2=scale2,
        now=now,
    )
    result = _branch.evaluate(inputs)
    payload = {
        "device_id": device_id,
        "decision": result.decision_name,
        "l_news": result.l_news,
        "s": result.s,
        "s_max": result.s_max,
        "completeness": result.completeness,
        "missing": result.missing,
        "needs_confirmation": result.needs_confirmation,
        "reasons": result.reasons,
        "algorithm_version": ALGORITHM_VERSION,
        "timestamp": int(now),
    }
    publish_json(NEWS2_DECISION, payload)
    LOGGER.info("%s", json.dumps(payload, default=str))


def handle(topic: str, payload: dict) -> None:
    if topic == MANUAL_INPUT or topic.endswith("/manual"):
        device_id = str(payload["device_id"])
        name = str(payload["name"])
        now = int(time.time())
        ttl_h = manual_ttl_hours(int(payload.get("s", 0)), int(payload.get("s_max", 0)))
        if name == "on_oxygen":
            until = None
        else:
            until = now + ttl_h * 3600
        db = SessionLocal()
        db.add(
            ManualVital(
                device_id=device_id,
                name=name,
                value=str(payload["value"]),
                valid_until=until,
                entered_at=now,
            )
        )
        db.commit()
        db.close()
        _publish(device_id)
        return
    device_id = str(payload["device_id"])
    kind = str(payload.get("kind", "ppg"))
    _auto.setdefault(device_id, {})[kind] = payload
    _publish(device_id)


def main() -> None:
    run_subscriber("news2", [SIGNAL, MANUAL_INPUT], handle)


if __name__ == "__main__":
    main()
