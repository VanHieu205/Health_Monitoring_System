"""Run the full ML pipeline for one or all FL architectures.

Examples
--------
    python scripts/train_models.py
    python scripts/train_models.py --arch arch.snn --epochs 12
    python scripts/train_models.py --data-dir data --no-synthetic
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from federated_learning.local_trainer import train_all, train_architecture


def main() -> None:
    parser = argparse.ArgumentParser(description="Train arch.snn / arch.sqi / arch.trend")
    parser.add_argument("--arch", default="all", choices=["all", "arch.snn", "arch.sqi", "arch.trend"])
    parser.add_argument("--data-dir", default=None, help="Folder with weda_fall/ ppg_dalia/ mimic_iv/")
    parser.add_argument("--artifact-dir", default="artifacts/fl")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--subjects", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-tune", action="store_true")
    parser.add_argument("--no-synthetic", action="store_true")
    args = parser.parse_args()
    kwargs = dict(
        data_dir=args.data_dir,
        artifact_dir=args.artifact_dir,
        epochs=args.epochs,
        n_subjects=args.subjects,
        tune=not args.no_tune,
        seed=args.seed,
        use_synthetic_if_missing=not args.no_synthetic,
    )
    if args.arch == "all":
        reports = train_all(**kwargs)
    else:
        reports = {args.arch: train_architecture(args.arch, **kwargs)}
    summary = {
        arch: {
            "source": rep.get("source"),
            "test": rep.get("test"),
            "checkpoint": rep.get("checkpoint"),
            "n_samples": rep.get("n_samples"),
        }
        for arch, rep in reports.items()
    }
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
