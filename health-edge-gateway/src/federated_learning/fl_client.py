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
    if os.getenv("FL_TRAIN", "").strip() in {"1", "true", "yes"}:
        from federated_learning.local_trainer import train_architecture
        from federated_learning.model_diff_encoder import encode_update
        from federated_learning.privacy_guard import check_update

        import torch

        reports = []
        for arch in allowed_architectures():
            report = train_architecture(
                arch,
                data_dir=os.getenv("FL_DATA_DIR") or None,
                epochs=int(os.getenv("FL_EPOCHS", "8")),
                n_subjects=int(os.getenv("FL_N_SUBJECTS", "8")),
                tune=os.getenv("FL_TUNE", "1").strip() not in {"0", "false", "no"},
            )
            ckpt = torch.load(report["checkpoint"], map_location="cpu")
            update = check_update(
                encode_update(
                    architecture=arch,
                    state_dict=ckpt["state_dict"],
                    n_samples=report["n_samples"],
                    model_version=str(ckpt.get("hparams")),
                )
            )
            reports.append(
                {
                    "architecture": arch,
                    "source": report.get("source"),
                    "test": report.get("test"),
                    "n_samples": update["n_samples"],
                    "update_bytes": len(json.dumps(update)),
                }
            )
        payload["status"] = "local_train_complete_not_sent"
        payload["reports"] = reports
    LOGGER.info("%s", json.dumps(payload, indent=2, default=str))
    if os.getenv("FL_ONCE", "1").strip() in {"1", "true", "yes"}:
        return
    LOGGER.info("Set FL_ONCE=0 and provide labeled feature tables before looping rounds.")


if __name__ == "__main__":
    main()
