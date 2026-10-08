"""Cold-path FL client: TinyML fall + PPG SQI only.

Does not federate NEWS2 cut-points, fusion tables, or a disease score.
Training runs on the Pi; the watch only infers. This process is safe
to start without a cloud server: it logs the round contract and exits
if the aggregator is unreachable.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from algorithms.news2 import (
    FL_ARCHITECTURE_SNN,
    FL_ARCHITECTURE_SQI,
    FL_ARCHITECTURE_TREND,
)
from common.config import load_gateway_env

load_gateway_env()
LOGGER = logging.getLogger("fl_client")

ALLOWED = frozenset({FL_ARCHITECTURE_SNN, FL_ARCHITECTURE_SQI, FL_ARCHITECTURE_TREND})


def allowed_architectures() -> tuple[str, ...]:
    raw = os.getenv(
        "FL_ARCHITECTURES",
        f"{FL_ARCHITECTURE_SNN},{FL_ARCHITECTURE_SQI},{FL_ARCHITECTURE_TREND}",
    )
    names = tuple(part.strip() for part in raw.split(",") if part.strip())
    bad = [name for name in names if name not in ALLOWED]
    if bad:
        raise ValueError(f"FL architecture not allowed in this phase: {bad}")
    return names


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    host = os.getenv("FL_SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("FL_SERVER_PORT", "50051"))
    payload = {
        "role": "edge_fl_client",
        "architectures": allowed_architectures(),
        "server": f"{host}:{port}",
        "trains_on": "labeled IMU/PPG features at the Pi, never raw waveforms",
        "does_not_train": [
            "NEWS2 cut-points",
            "NEWS2 risk bands",
            "fusion max() rules",
        ],
        "status": "cold_path_idle_no_labeled_buffer",
    }
    LOGGER.info("%s", json.dumps(payload, indent=2))
    if os.getenv("FL_ONCE", "1").strip() in {"1", "true", "yes"}:
        return
    LOGGER.info("Set FL_ONCE=0 and provide labeled feature tables before looping rounds.")


if __name__ == "__main__":
    main()
