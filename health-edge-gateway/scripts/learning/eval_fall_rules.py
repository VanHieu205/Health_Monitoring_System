"""Score fall rules on whole WEDA trials (FR-01, FR-02).

LOSO picks thresholds without the held-out subject. The seed-42 holdout
matches the SNN split. SNN only raises a missed impact to a fall; its
threshold is chosen on the validation subjects.

    python scripts/learning/eval_fall_rules.py --data-dir data
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))

from domain.fall_events import TARGET_SENSITIVITY, assert_event_rules
from learning.training.data.catalog import spec_for_architecture
from learning.training.data.fetch import raw_dir
from learning.training.data.prepare.weda import load_weda_trials
from learning.training.fall_rule_eval import (
    choose_snn_tau,
    evaluate_split,
    peak_windows,
    run_loso,
    score_trials,
    select_rules,
    split_subjects,
)
from learning.training.models.snn_lif import MotionSNN
from learning.training.preprocess.snn import clip_imu_g, delta_encode, encode_motion
from learning.training.train_loop import _fall_probability


def main() -> None:
    parser = argparse.ArgumentParser(description="Event-level fall rules on WEDA trials")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--checkpoint", default="artifacts/learning/arch_snn/model.pt")
    parser.add_argument("--out", default="artifacts/learning/arch_snn/fall_rules.json")
    args = parser.parse_args()
    assert_event_rules()

    root = Path(args.data_dir)
    spec = spec_for_architecture("arch.snn", root)
    scored = score_trials(load_weda_trials(raw_dir(spec, root)))
    groups = split_subjects([t.subject for t in scored], seed=args.seed)
    by_group = {
        name: [t for t in scored if t.subject in set(names)]
        for name, names in groups.items()
    }
    pool = by_group["train"] + by_group["val"]
    smv_rule, iso_rule = select_rules(pool)

    rows = []
    for rule in (smv_rule, iso_rule):
        train_val = _public(evaluate_split(pool, rule))
        se = train_val["sensitivity"]
        rows.append(
            {
                "name": rule.name,
                "thresholds": rule.as_dict(),
                "constraint_met_on_train_val": se is not None and se + 1e-12 >= TARGET_SENSITIVITY,
                "train_val": train_val,
                "test": evaluate_split(by_group["test"], rule),
            }
        )

    snn = _snn_row(args.checkpoint, scored, by_group, iso_rule)
    report = {
        "seed": args.seed,
        "subjects": groups,
        "cancel_window": "not_applied",
        "rule": (
            "isolated_peak: SMV peak, posture change, and at most N other "
            "impacts within ±3 s. Ten-second inactivity is not used: WEDA "
            "files end too soon and the wrist stays above 0.08 g."
        ),
        "selection": (
            "LOSO chooses thresholds on every subject except the one being "
            "scored. The seed-42 rows use train+val only. Prefer Se>=0.90, "
            "then the lowest false alarms per ADL trial."
        ),
        "loso": _strip_folds(run_loso(scored)),
        "holdout": rows,
        "snn_escalation": snn,
    }
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


def _snn_row(path: str, scored, by_group, rule) -> dict:
    ckpt_path = Path(path)
    if not ckpt_path.is_file():
        return {"available": False, "reason": f"missing checkpoint {ckpt_path}"}
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    hparams = ckpt.get("hparams") or {}
    beta = float(hparams.get("beta", 0.9))
    n_in = int(ckpt["state_dict"]["hidden.linear.weight"].shape[1])
    n_out = int(ckpt["state_dict"]["output.linear.weight"].shape[0])
    model = MotionSNN(n_in=n_in, n_out=n_out, beta=beta)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    windows = clip_imu_g(peak_windows(scored))
    spec = (float(hparams.get("delta_acc", 0.05)), float(hparams.get("delta_gyr", 10.0)))
    band = float(hparams.get("rhythm_band", 0.15))
    spikes = encode_motion(windows, spec, band) if n_in > 12 else delta_encode(windows, spec)
    with torch.no_grad():
        logits = model(torch.tensor(spikes)).numpy()
    scores = _fall_probability(logits)
    index = {id(t): i for i, t in enumerate(scored)}

    def take(group):
        idx = [index[id(t)] for t in group]
        return np.asarray([scores[i] for i in idx])

    tau = choose_snn_tau(by_group["val"], rule, take(by_group["val"]))
    return {
        "available": True,
        "role": "raises possible_fall to fall only; never clears a rule fall",
        "tau": tau,
        "delta_acc": hparams.get("delta_acc"),
        "delta_gyr": hparams.get("delta_gyr"),
        "test": evaluate_split(by_group["test"], rule, scores=take(by_group["test"]), snn_tau=tau),
    }


def _public(metrics: dict) -> dict:
    return {k: v for k, v in metrics.items() if k != "per_subject"}


def _strip_folds(loso: dict) -> dict:
    """Drop per-fold subject tables from the printed report; medians stay."""
    out = {"protocol": loso["protocol"], "n_subjects": loso["n_subjects"]}
    for name in ("smv_only", "isolated_peak"):
        row = dict(loso[name])
        row.pop("folds", None)
        out[name] = row
    return out


if __name__ == "__main__":
    main()
