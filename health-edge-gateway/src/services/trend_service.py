"""branch_trend: optional p_det → L_trend (cap 2). Cold-path model can fill p_det later."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC))

from algorithms.news2 import ALGORITHM_VERSION
from algorithms.trend_branch import TrendBranch
from common.config import load_gateway_env
from common.topics import NEWS2_DECISION, TREND_DECISION
from services.bus import publish_json
from services.mqtt_loop import run_subscriber

load_gateway_env()
LOGGER = logging.getLogger("trend")
_branch = TrendBranch()


def handle(_topic: str, payload: dict) -> None:
    p_det = payload.get("p_det")
    l_news = int(payload.get("l_news") or 0)
    result = _branch.evaluate(p_det=p_det, l_news=l_news)
    out = {
        "device_id": payload.get("device_id"),
        "l_trend": result.l_trend,
        "p_det": result.p_det,
        "l_news": l_news,
        "reasons": result.reasons,
        "algorithm_version": ALGORITHM_VERSION,
        "timestamp": payload.get("timestamp"),
    }
    publish_json(TREND_DECISION, out)
    LOGGER.info("%s", json.dumps(out, default=str))


def main() -> None:
    run_subscriber("trend", [NEWS2_DECISION], handle)


if __name__ == "__main__":
    main()
