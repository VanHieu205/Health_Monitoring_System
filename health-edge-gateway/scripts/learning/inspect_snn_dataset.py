"""Describe the prepared WEDA windows used by arch.snn.

Reads data/weda_fall/windows.npz only. Does not train and does not refit
anything on the test subjects. The subject split matches train_models.py
with the same seed.

    python scripts/learning/inspect_snn_dataset.py --data-dir data --seed 42
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))

from learning.training.config import SNN_CLASSES
from learning.training.preprocess import subject_holdout

NAMES = {i: name for i, name in enumerate(SNN_CLASSES)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect prepared WEDA windows for arch.snn")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    path = Path(args.data_dir) / "weda_fall" / "windows.npz"
    if not path.is_file():
        raise SystemExit(f"Missing {path}. Import WEDA first.")

    blob = np.load(path, allow_pickle=True)
    x = blob["X"].astype(np.float32)
    y = blob["y"].astype(np.int64)
    subject = blob["subject"].astype(str)
    if y.size and int(y.min()) >= 1 and int(y.max()) <= len(SNN_CLASSES):
        y = y - 1
    smv = np.sqrt((x[:, :, :3].astype(np.float64) ** 2).sum(axis=-1)).max(axis=1)
    gyr = np.sqrt((x[:, :, 3:].astype(np.float64) ** 2).sum(axis=-1)).max(axis=1)

    print(f"file: {path}")
    print(f"windows: {len(y)}  subjects: {len(np.unique(subject))}  shape: {tuple(x.shape)}")
    print(f"trained classes: {list(SNN_CLASSES)}")
    print("overlap: 2 s window, 1 s stride. Same person stays in one split, so overlap is not leakage.")
    print()
    _counts("all", y)
    print()
    _smv_table("SMV peak (g) by class", y, smv)
    print()
    _smv_table("gyro peak (deg/s) by class", y, gyr)
    print()
    walk = y == 1
    fall = y == 2
    print(
        f"walk windows with SMV peak >= 2.5 g: {int((walk & (smv >= 2.5)).sum())} / {int(walk.sum())}"
        "  (walk is D01, D03, D11; impact_adl is jog, collapse, crouch, stumble, jump, hit, clap)"
    )
    print(
        f"fall windows with SMV peak < 2.0 g: {int((fall & (smv < 2.0)).sum())} / {int(fall.sum())}"
        "  (annotated impact still looks mild)"
    )
    print()

    corpus = {"X": x, "y": y, "subject": subject}
    split = subject_holdout(corpus, seed=args.seed)
    for name, yy, ss in (
        ("train", split.y_train, split.subject_train),
        ("val", split.y_val, split.subject_val),
        ("test", split.y_test, split.subject_test),
    ):
        people = sorted(set(ss.tolist()))
        print(f"== {name}  n={len(yy)}  subjects={people}")
        _counts(name, yy)
        _people(ss, yy)
        print()


def _counts(title: str, y: np.ndarray) -> None:
    total = max(1, len(y))
    parts = []
    for k, name in NAMES.items():
        n = int((y == k).sum())
        parts.append(f"{name}={n} ({n / total:.1%})")
    print(f"{title}: " + "  ".join(parts))


def _smv_table(title: str, y: np.ndarray, values: np.ndarray) -> None:
    print(title)
    print(f"{'class':<12} {'n':>6} {'p50':>8} {'p95':>8} {'max':>8}")
    for k, name in NAMES.items():
        col = values[y == k]
        if len(col) == 0:
            print(f"{name:<12} {0:6d}")
            continue
        print(
            f"{name:<12} {len(col):6d} {np.median(col):8.2f} "
            f"{np.quantile(col, 0.95):8.2f} {col.max():8.2f}"
        )


def _people(subject: np.ndarray, y: np.ndarray) -> None:
    header = f"{'id':<6} {'group':<6} " + " ".join(f"{name[:6]:>6}" for name in SNN_CLASSES)
    print(header)
    for sid in sorted(set(subject.tolist())):
        mask = subject == sid
        n = int(sid[1:])
        group = "young" if n <= 14 else "elder"
        counts = " ".join(f"{int((y[mask] == k).sum()):6d}" for k in range(len(SNN_CLASSES)))
        print(f"{sid:<6} {group:<6} {counts}")


if __name__ == "__main__":
    main()
