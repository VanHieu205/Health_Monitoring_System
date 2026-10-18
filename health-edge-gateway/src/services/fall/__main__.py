"""branch_fall: confirm FALL_CANDIDATE from MOTION / BUTTON (event-driven)."""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC))

from domain.fall_confirm import ACTIVE_CLASSES, RESTISH_CLASSES, FallConfirmEngine
from domain.news2 import ALGORITHM_VERSION
from runtime.config import load_gateway_env
from contracts.topics import FALL_DECISION, WATCH_BUTTON, WATCH_FALL, WATCH_MOTION
from persistence.db_models import FallEvent, SessionLocal
from services.branches.snn import read as read_motion
from runtime.bus import publish_json
from runtime.mqtt import device_id_from_topic, run_subscriber

load_gateway_env()
LOGGER = logging.getLogger("fall")
_engine = FallConfirmEngine()


@dataclass
class FallState:
    t_impact: float | None = None
    last_motion: float | None = None
    consecutive_active_s: float = 0.0
    consecutive_rest_s: float = 0.0
    button_cancel: bool = False
    new_impact: bool = False
    last_class: str | None = None


_state: dict[str, FallState] = {}


def _publish(device_id: str, result, ts: int, extra: dict | None = None) -> None:
    payload = {
        "device_id": device_id,
        "decision": result.decision.value,
        "l_fall": result.l_fall,
        "reasons": result.reasons,
        "algorithm_version": ALGORITHM_VERSION,
        "timestamp": ts,
        **(extra or {}),
    }
    db = SessionLocal()
    db.add(
        FallEvent(
            timestamp=ts,
            device_id=device_id,
            decision=result.decision.value,
            l_fall=result.l_fall,
            smv_peak_g=(extra or {}).get("smv_peak_g"),
            reasons=json.dumps(result.reasons),
        )
    )
    db.commit()
    db.close()
    publish_json(FALL_DECISION, payload)
    LOGGER.info("%s", json.dumps(payload, default=str))


def handle(topic: str, payload: dict) -> None:
    device_id = str(payload.get("device_id") or device_id_from_topic(topic))
    kind = topic.rsplit("/", 1)[-1]
    now = float(payload.get("ts_ms") or time.time() * 1000) / 1000.0
    st = _state.setdefault(device_id, FallState())

    if kind == "fall_candidate":
        st.t_impact = now
        st.consecutive_active_s = 0.0
        st.consecutive_rest_s = 0.0
        st.button_cancel = False
        st.new_impact = True
        st.last_motion = now
        result = _engine.evaluate(elapsed_s=0.0, has_candidate=True)
        if result.ready:
            _publish(device_id, result, int(now), {"smv_peak_g": payload.get("smv_peak_g")})
        return

    if st.t_impact is None:
        return

    if kind == "button" and payload.get("action") in {"cancel", "im_ok", "huy"}:
        st.button_cancel = True
    elif kind == "motion":
        motion = read_motion(payload)
        cls_ = motion.label or "unknown"
        dt = 0.0 if st.last_motion is None else max(0.0, now - st.last_motion)
        st.last_motion = now
        if cls_ in ACTIVE_CLASSES:
            st.consecutive_active_s += dt
            st.consecutive_rest_s = 0.0
        elif cls_ in RESTISH_CLASSES:
            st.consecutive_rest_s += dt
            st.consecutive_active_s = 0.0
        else:
            st.consecutive_active_s = 0.0
            st.consecutive_rest_s = 0.0
        st.new_impact = False
        st.last_class = cls_

    elapsed = now - st.t_impact
    missing = st.last_motion is not None and (now - st.last_motion) > 10.0 and elapsed > 5.0
    result = _engine.evaluate(
        elapsed_s=elapsed,
        consecutive_active_s=st.consecutive_active_s,
        consecutive_rest_s=st.consecutive_rest_s,
        button_cancel=st.button_cancel,
        new_impact=st.new_impact,
        packets_missing=missing,
        has_candidate=True,
    )
    if result.ready:
        _publish(device_id, result, int(now))
        _state.pop(device_id, None)


def main() -> None:
    run_subscriber("fall", [WATCH_FALL, WATCH_MOTION, WATCH_BUTTON], handle)


if __name__ == "__main__":
    main()
