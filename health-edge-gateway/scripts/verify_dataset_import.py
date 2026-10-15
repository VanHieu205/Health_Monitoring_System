"""Build a tiny fake WEDA + MIMIC CSV and check prepare → loader (no network)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from federated_learning.training.data.importer import import_dataset
from federated_learning.training.data.loaders import load_snn, load_trend


def _write_xyz(path: Path, n: int = 220, peak: bool = False) -> None:
    t = np.arange(n, dtype=np.float32)
    acc = np.stack([np.zeros(n), np.zeros(n), np.ones(n)], axis=1)
    if peak:
        acc[80:83, 2] = 3.2
    np.savetxt(path, np.column_stack([t, acc]), delimiter=",")


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "artifacts" / "dataset_fixture"
    weda_raw = root / "raw" / "weda_fall" / "dataset" / "50Hz"
    (weda_raw / "D01").mkdir(parents=True, exist_ok=True)
    (weda_raw / "F01").mkdir(parents=True, exist_ok=True)
    _write_xyz(weda_raw / "D01" / "U01_R01_accel.csv")
    _write_xyz(weda_raw / "D01" / "U01_R01_gyro.csv")
    _write_xyz(weda_raw / "F01" / "U02_R01_accel.csv", peak=True)
    _write_xyz(weda_raw / "F01" / "U02_R01_gyro.csv", peak=True)

    npz = import_dataset("weda_fall", data_root=root, skip_fetch=True, force=True)
    snn = load_snn(root, n_subjects=2, seed=0, synthetic_ok=False)
    assert snn["source"] == "weda_fall"
    assert snn["X"].shape[1:] == (100, 6)
    assert set(snn["y"].tolist()) <= {2, 3}

    csv_path = root / "vitals.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["subject_id", "charttime", "hr", "spo2", "rr", "temperature"])
        for i in range(20):
            hr = 75 + (i if i >= 10 else 0)
            spo2 = 98 - (0.4 * max(0, i - 9))
            w.writerow(["P1", f"2020-01-01 {i:02d}:00:00", hr, spo2, 16 + i // 5, 36.8])
    tnpz = import_dataset("mimic_iv", data_root=root, from_csv=csv_path, force=True)
    trend = load_trend(root, n_subjects=1, seed=0, synthetic_ok=False)
    assert trend["source"] == "mimic_iv"
    assert trend["X"].shape[1] == 13
    print("WEDA", npz, snn["X"].shape, "labels", sorted(set(snn["y"].tolist())))
    print("MIMIC", tnpz, trend["X"].shape)
    print("ALL OK")


if __name__ == "__main__":
    main()
