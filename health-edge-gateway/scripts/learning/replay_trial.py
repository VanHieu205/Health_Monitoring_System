"""Replay one real WEDA trial through the saved SNN. No hardware.

Reads a raw accel/gyro pair, cuts the same 2 s windows as training, and
prints the class of each window. Pick a seed-42 test subject
(U07, U08, U10, U21, U28) so the person was not in training.

    python scripts/learning/replay_trial.py --code F01 --subject U07
    python scripts/learning/replay_trial.py --code D01 --subject U07
    python scripts/learning/replay_trial.py --code D10 --subject U07 --trial 1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))

from learning.training.config import SNN_CLASSES
from learning.training.data.prepare.weda import (
    STRIDE,
    WIN,
    _find_50hz,
    _group_trials,
    _gyro_on_grid,
    _read_xyz,
    _uniform_grid,
)
from learning.training.models.snn_lif import MotionSNN
from learning.training.preprocess.snn import clip_imu_g, encode_motion
from learning.training.train_loop import _fall_probability, predict_snn

MARK = {"sit_stand": "S", "walk": "W", "fall_like": "F", "impact_adl": "A"}
TEST_SUBJECTS = ("U07", "U08", "U10", "U21", "U28")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay one WEDA trial through arch.snn")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--checkpoint", default="artifacts/learning/arch_snn/model.pt")
    parser.add_argument("--code", required=True, help="Activity folder, e.g. F01 or D10")
    parser.add_argument("--subject", required=True, help="Subject id, e.g. U07")
    parser.add_argument("--trial", type=int, default=1, help="Recording index Rxx")
    args = parser.parse_args()

    code = args.code.upper()
    subject = args.subject.upper()
    if not subject.startswith("U"):
        subject = f"U{int(subject):02d}"
    user = f"{int(subject[1:]):02d}"
    trial = f"{args.trial:02d}"

    hz = _find_50hz(Path(args.data_dir) / "raw" / "weda_fall")
    if hz is None:
        raise SystemExit("No dataset/50Hz folder under data/raw/weda_fall")
    files = _group_trials(hz / code).get((user, trial))
    if not files:
        raise SystemExit(f"No {code}/{subject}_R{trial} under {hz}")

    acc_t, acc = _read_xyz(files.get("accel"), is_accel=True)
    gyr_t, gyr = _read_xyz(files.get("gyro"), is_accel=False)
    grid, acc_u = _uniform_grid(acc_t, acc)
    if grid is None or acc_u is None:
        raise SystemExit("Trial is too short for a 2 s window")
    imu = np.concatenate([acc_u, _gyro_on_grid(grid, gyr_t, gyr)], axis=1).astype(np.float32)
    windows = np.stack([imu[s : s + WIN] for s in range(0, len(imu) - WIN + 1, STRIDE)])

    ckpt = torch.load(Path(args.checkpoint), map_location="cpu", weights_only=False)
    hp = ckpt["hparams"]
    n_in = int(ckpt["state_dict"]["hidden.linear.weight"].shape[1])
    n_out = int(ckpt["state_dict"]["output.linear.weight"].shape[0])
    model = MotionSNN(n_in=n_in, n_out=n_out, beta=float(hp.get("beta", 0.9)))
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    spikes = encode_motion(
        clip_imu_g(windows),
        (float(hp.get("delta_acc", 0.05)), float(hp.get("delta_gyr", 10.0))),
        float(hp.get("rhythm_band", 0.15)),
    )
    if spikes.shape[-1] != n_in:
        raise SystemExit(f"Checkpoint expects {n_in} channels, encoder produced {spikes.shape[-1]}")
    logits = model(torch.tensor(spikes)).detach().numpy()
    smv = np.sqrt((windows[:, :, :3].astype(np.float64) ** 2).sum(axis=-1)).max(axis=1)
    tau = float(hp.get("fall_tau", 0.5))
    floor = float(hp.get("smv_floor") or 0.0)
    pred = predict_snn(logits, tau, smv=smv, smv_floor=floor)
    prob = _fall_probability(logits)

    names = [SNN_CLASSES[int(i)] for i in pred]
    print(f"file: {code}/{subject}_R{trial}  windows={len(names)}  tau={tau:.2f}  smv_floor={floor:.2f}")
    if subject in TEST_SUBJECTS:
        print("subject is in the seed-42 test split")
    else:
        print("subject was used in train or val; this replay is not a held-out check")
    counts = {name: names.count(name) for name in SNN_CLASSES}
    print(" ".join(f"{name}={counts[name]}" for name in SNN_CLASSES))
    print("".join(MARK[name] for name in names))
    print("S=sit  W=walk  F=fall  A=impact")
    top = int(np.argmax(prob))
    print(
        f"strongest fall window: t={top * STRIDE / 50:.1f}s  "
        f"P(fall)={prob[top]:.2f}  SMV={smv[top]:.2f}g  class={names[top]}"
    )


if __name__ == "__main__":
    main()
