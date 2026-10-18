"""Profile raw WEDA trials before the three-class merge.

Answers whether the current windowing can support fall recall above 90%,
and which activity codes overlap a fall. The SMV cutoff that first reaches
90% sensitivity is chosen on the training subjects only. Validation and
test numbers are a check; do not slide the cutoff to improve the test line.

    python scripts/learning/analyze_weda_preprocess.py --data-dir data --seed 42
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))

from learning.training.data.prepare.weda import (
    FS,
    STRIDE,
    WIN,
    WEDA_LABEL,
    _find_50hz,
    _group_trials,
    _gyro_on_grid,
    _keep_fall_window,
    _load_fall_timestamps,
    _read_xyz,
    _uniform_grid,
)
from learning.training.preprocess import subject_holdout

CODE_NAME = {
    "D01": "walk",
    "D02": "jog",
    "D03": "stairs",
    "D04": "sit-stand",
    "D05": "collapse-sit",
    "D06": "crouch",
    "D07": "stumble",
    "D08": "jump",
    "D09": "hit-table",
    "D10": "clap",
    "D11": "door",
    "F01": "fall-slip-fwd",
    "F02": "fall-slip-side",
    "F03": "fall-slip-back",
    "F04": "fall-trip",
    "F05": "fall-sit-back",
    "F06": "fall-sit-fwd",
    "F07": "fall-sit-back2",
    "F08": "fall-sit-side",
}
MERGE = {0: "excluded", 1: "sit_stand", 2: "walk", 3: "fall_like", 4: "impact_adl"}
EXCLUDED: set[str] = set()


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile raw WEDA for fall-recall preprocess")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    root = Path(args.data_dir)
    raw = root / "raw" / "weda_fall"
    hz = _find_50hz(raw)
    if hz is None:
        raise SystemExit(f"No dataset/50Hz under {raw}")

    trials, gaps = _scan(hz, _load_fall_timestamps(raw))
    lines = _report(trials, gaps, args.seed)
    text = "\n".join(lines) + "\n"
    out = root.parent / "artifacts" / "learning" / "arch_snn" / "raw_profile.txt"
    # data-dir is health-edge-gateway/data, artifacts live beside it.
    if root.name == "data":
        out = root.parent / "artifacts" / "learning" / "arch_snn" / "raw_profile.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"wrote {out}")


def _scan(hz: Path, stamps: dict) -> tuple[list[dict], dict]:
    trials: list[dict] = []
    gaps = {
        "no_accel": 0,
        "no_gyro": 0,
        "too_short": 0,
        "backward_steps": 0,
        "gaps_over_100ms": 0,
        "files": 0,
    }
    for code_dir in sorted(p for p in hz.iterdir() if p.is_dir()):
        code = code_dir.name.upper()
        if code not in WEDA_LABEL and code not in EXCLUDED:
            continue
        for (user, trial), files in _group_trials(code_dir).items():
            gaps["files"] += 1
            if "accel" not in files:
                gaps["no_accel"] += 1
                continue
            if "gyro" not in files:
                gaps["no_gyro"] += 1
            acc_t, acc = _read_xyz(files.get("accel"), is_accel=True)
            gyr_t, gyr = _read_xyz(files.get("gyro"), is_accel=False)
            if acc_t is None or acc is None:
                gaps["too_short"] += 1
                continue
            dt = np.diff(acc_t.astype(np.float64))
            gaps["backward_steps"] += int((dt <= 0).sum())
            gaps["gaps_over_100ms"] += int((dt > 0.1).sum())
            grid, acc_u = _uniform_grid(acc_t, acc)
            if grid is None or acc_u is None:
                gaps["too_short"] += 1
                continue
            gyr_u = _gyro_on_grid(grid, gyr_t, gyr)
            smv = np.sqrt((acc_u.astype(np.float64) ** 2).sum(axis=1))
            gpeak = np.sqrt((gyr_u.astype(np.float64) ** 2).sum(axis=1))
            key = f"{code}/U{int(user):02d}_R{int(trial):02d}"
            impact = stamps.get(key)
            peak = int(np.argmax(smv))
            windows = []
            for start in range(0, len(smv) - WIN + 1, STRIDE):
                kept = True
                if code.startswith("F") and impact is not None:
                    kept = _keep_fall_window(grid, start, impact, peak)
                windows.append((kept, float(smv[start : start + WIN].max()), float(gpeak[start : start + WIN].max())))
            inside = outside = None
            if impact is not None:
                mask = (grid >= impact[0]) & (grid <= impact[1])
                if mask.any():
                    inside = float(smv[mask].max())
                if (~mask).any():
                    outside = float(smv[~mask].max())
            trials.append(
                {
                    "code": code,
                    "subject": f"U{int(user):02d}",
                    "label": WEDA_LABEL.get(code, 0),
                    "duration": float(len(grid) - 1) / FS,
                    "smv_peak": float(smv.max()),
                    "gyro_peak": float(gpeak.max()),
                    "impact_in": inside,
                    "impact_out": outside,
                    "windows": windows,
                    "gyro_missing": gyr is None,
                }
            )
    return trials, gaps


def _report(trials: list[dict], gaps: dict, seed: int) -> list[str]:
    lines = [
        "WEDA raw profile (50 Hz folder, accel in g, gyro in deg/s)",
        f"trials used: {len(trials)}",
        "",
        "== missing / irregular raw ==",
        f"grouped files: {gaps['files']}",
        f"no accel file: {gaps['no_accel']}",
        f"no gyro file: {gaps['no_gyro']}",
        f"too short for a 2 s window: {gaps['too_short']}",
        f"backward or duplicate accel timestamps: {gaps['backward_steps']}",
        f"accel gaps longer than 100 ms: {gaps['gaps_over_100ms']}",
        f"resampled trials whose gyro was missing (zeros): {sum(t['gyro_missing'] for t in trials)}",
        "",
        "== per activity code, whole trial ==",
        f"{'code':<6} {'name':<16} {'merge':<10} {'n':>4} {'sec_p50':>8} {'smv_p50':>8} {'smv_p95':>8} {'gyr_p50':>8} {'win>=2.5g':>10}",
    ]
    by_code: dict[str, list[dict]] = {}
    for trial in trials:
        by_code.setdefault(trial["code"], []).append(trial)
    for code in sorted(by_code):
        group = by_code[code]
        peaks = np.array([t["smv_peak"] for t in group])
        gyros = np.array([t["gyro_peak"] for t in group])
        durs = np.array([t["duration"] for t in group])
        strong, total = _window_counts(group, lambda w: w[0] and w[1] >= 2.5)
        lines.append(
            f"{code:<6} {CODE_NAME.get(code, ''):<16} {MERGE[group[0]['label']]:<10} {len(group):4d} "
            f"{np.median(durs):8.1f} {np.median(peaks):8.2f} {np.quantile(peaks, 0.95):8.2f} "
            f"{np.median(gyros):8.0f} {strong:4d}/{total:<5d}"
        )

    lines += ["", "== fall trials: inside vs outside the annotated impact =="]
    lines.append(f"{'code':<6} {'n':>4} {'in_p50':>8} {'out_p50':>8} {'kept':>6} {'dropped':>8} {'kept<2g':>8}")
    for code in sorted(c for c in by_code if c.startswith("F")):
        group = by_code[code]
        inside = [t["impact_in"] for t in group if t["impact_in"] is not None]
        outside = [t["impact_out"] for t in group if t["impact_out"] is not None]
        kept = dropped = mild = 0
        for trial in group:
            for flag, smv, _gyro in trial["windows"]:
                if flag:
                    kept += 1
                    mild += int(smv < 2.0)
                else:
                    dropped += 1
        in_p = f"{np.median(inside):8.2f}" if inside else f"{'n/a':>8}"
        out_p = f"{np.median(outside):8.2f}" if outside else f"{'n/a':>8}"
        lines.append(f"{code:<6} {len(group):4d} {in_p} {out_p} {kept:6d} {dropped:8d} {mild:8d}")

    lines += [
        "",
        "== walk merge: which codes produce SMV >= 2.5 g windows ==",
    ]
    for code in ("D01", "D02", "D03", "D07", "D08", "D09", "D10", "D11"):
        if code not in by_code:
            continue
        strong, total = _window_counts(by_code[code], lambda w: w[0] and w[1] >= 2.5)
        share = strong / total if total else 0.0
        lines.append(f"{code} {CODE_NAME[code]:<12} {strong:4d}/{total:<5d}  ({share:.0%} of its windows)")

    x, y, subject, smv = _flat_windows(trials)
    corpus = {"X": x, "y": y, "subject": subject}
    split = subject_holdout(corpus, seed=seed)
    lines += [
        "",
        "== SMV-only fall rule, cutoff fit on train subjects to reach 90% sensitivity ==",
        "Predict fall when the 2 s SMV peak >= cutoff. This is a ceiling check, not the SNN.",
    ]
    train_mask = np.isin(subject, split.subject_train)
    fall = y == 3
    cutoff = _cutoff_for_sensitivity(smv[train_mask & fall], target=0.90)
    lines.append(f"train cutoff for >=90% of train fall windows: {cutoff:.2f} g")
    for name, people in (
        ("train", split.subject_train),
        ("val", split.subject_val),
        ("test", split.subject_test),
    ):
        mask = np.isin(subject, people)
        lines.append(_rule_line(name, y[mask], smv[mask], cutoff))
    lines += [
        "",
        "Read test as a check only. Retuning this cutoff on test recall is leakage.",
        "D02, D05, D06, D07, D08, D09 and D10 are impact_adl on every split.",
        "D01, D03 and D11 stay walk. D04 stays sit_stand. Only F01-F08 are falls.",
        "Dropping fall windows under 2 g raises recall by changing the positive definition; report that separately.",
    ]
    return lines


def _window_counts(group: list[dict], pred) -> tuple[int, int]:
    strong = total = 0
    for trial in group:
        for window in trial["windows"]:
            if not window[0]:
                continue
            total += 1
            strong += int(pred(window))
    return strong, total


def _flat_windows(trials: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    xs, ys, ss, peaks = [], [], [], []
    for trial in trials:
        if trial["label"] == 0:
            continue
        for kept, smv, _gyro in trial["windows"]:
            if not kept:
                continue
            xs.append(0.0)
            ys.append(trial["label"])
            ss.append(trial["subject"])
            peaks.append(smv)
    return (
        np.zeros((len(ys), 1), dtype=np.float32),
        np.asarray(ys, dtype=np.int64),
        np.asarray(ss),
        np.asarray(peaks, dtype=np.float64),
    )


def _cutoff_for_sensitivity(fall_peaks: np.ndarray, target: float) -> float:
    if len(fall_peaks) == 0:
        return 2.5
    ordered = np.sort(fall_peaks)
    # Lowest peaks must be included to reach the target sensitivity.
    index = int(np.floor((1.0 - target) * len(ordered)))
    index = min(max(index, 0), len(ordered) - 1)
    return float(ordered[index])


def _rule_line(name: str, y: np.ndarray, smv: np.ndarray, cutoff: float) -> str:
    pred = smv >= cutoff
    fall = y == 3
    hit = int((pred & fall).sum())
    positive = int(fall.sum())
    false = int((pred & ~fall).sum())
    negative = int((~fall).sum())
    se = hit / positive if positive else 0.0
    fpr = false / negative if negative else 0.0
    return (
        f"{name:<5} fall_windows={positive:4d}  sensitivity={se:.3f}  "
        f"false_alarms={false:4d}/{negative:<4d} (FPR={fpr:.3f})"
    )


if __name__ == "__main__":
    main()
