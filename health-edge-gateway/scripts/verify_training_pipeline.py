"""Smoke test: EDA + train + evaluate all three architectures on tiny synthetic data."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from federated_learning.local_trainer import train_architecture
from federated_learning.model_diff_encoder import encode_update
from federated_learning.privacy_guard import PrivacyError, check_update
import torch


def main() -> None:
    reports = {}
    for arch in ("arch.snn", "arch.sqi", "arch.trend"):
        report = train_architecture(
            arch,
            artifact_dir="artifacts/fl_smoke",
            epochs=3,
            n_subjects=5,
            tune=False,
            seed=0,
        )
        assert report["n_samples"] > 0
        assert Path(report["checkpoint"]).is_file()
        assert (Path(report["checkpoint"]).parent / "eda.md").is_file()
        ckpt = torch.load(report["checkpoint"], map_location="cpu")
        update = check_update(
            encode_update(
                architecture=arch,
                state_dict=ckpt["state_dict"],
                n_samples=report["n_samples"],
            )
        )
        assert update["architecture"] == arch
        try:
            check_update({**update, "waveform": [1, 2, 3]})
            raise AssertionError("privacy guard should reject waveforms")
        except PrivacyError:
            pass
        reports[arch] = report["test"]
        print(arch, "OK", report["test"])

    assert reports["arch.trend"].get("l_trend_never_emergency") is True
    print("ALL OK")


if __name__ == "__main__":
    main()
