"""Fetch and prepare datasets from GitHub, Kaggle, UCI, HTTP, or a local folder.

Examples
--------
    python scripts/learning/import_dataset.py --list
    python scripts/learning/import_dataset.py --dataset weda_fall
    python scripts/learning/import_dataset.py --dataset ppg_dalia --source http
    python scripts/learning/import_dataset.py --dataset mimic_iv --from-csv exports/vitals.csv
    python scripts/learning/import_dataset.py --dataset weda_fall --from-local D:\\data\\WEDA-FALL
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))

from learning.training.data.importer import import_dataset, list_datasets


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a training dataset into data/<id>/windows.npz")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dataset", help="id in the catalog (weda_fall, ppg_dalia, mimic_iv, or overlay)")
    parser.add_argument("--source", choices=["github", "kaggle", "http", "uci", "physionet", "local"])
    parser.add_argument("--from-csv", help="MIMIC / bedside vitals CSV")
    parser.add_argument("--from-local", help="Already-downloaded folder or zip")
    parser.add_argument("--data-dir", default=None, help="Root (default: health-edge-gateway/data)")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-fetch", action="store_true", help="Only prepare existing data/raw/<id>")
    args = parser.parse_args()
    root = Path(args.data_dir) if args.data_dir else None

    if args.list or not args.dataset:
        print(json.dumps(list_datasets(root), indent=2, ensure_ascii=True))
        if not args.dataset:
            return

    path = import_dataset(
        args.dataset,
        data_root=root,
        source_type=args.source,
        from_csv=Path(args.from_csv) if args.from_csv else None,
        from_local=Path(args.from_local) if args.from_local else None,
        force=args.force,
        skip_fetch=args.skip_fetch,
    )
    print(json.dumps({"dataset": args.dataset, "windows": str(path)}, indent=2))


if __name__ == "__main__":
    main()
