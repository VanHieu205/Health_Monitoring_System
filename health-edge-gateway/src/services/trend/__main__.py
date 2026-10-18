"""branch_trend: published p_det → L_trend, capped at 2."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC))

from domain.news2 import ALGORITHM_VERSION
from domain.trend_branch import TrendBranch
from runtime.config import load_gateway_env
from contracts.topics import NEWS2_DECISION, TREND_DECISION
from services.branches.trend import read as read_trend
from runtime.bus import publish_json
from runtime.mqtt import run_subscriber

load_gateway_env()
LOGGER = logging.getLogger("trend")
_branch = TrendBranch()


def handle(_topic: str, payload: dict) -> None:
    trend = read_trend(payload)
    l_news = int(payload.get("l_news") or 0)
    result = _branch.evaluate(p_det=trend.score, l_news=l_news)
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
