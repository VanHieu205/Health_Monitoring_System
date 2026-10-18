"""Exploratory reports written as JSON + Markdown (no plot dependency)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

from learning.training.config import SNN_CLASSES, SQI_FEATURES, TREND_FEATURES


def run_eda(architecture: str, corpus: dict, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    if architecture == "arch.snn":
        report = _eda_snn(corpus)
    elif architecture == "arch.sqi":
        report = _eda_sqi(corpus)
    else:
        report = _eda_trend(corpus)
    (out_dir / "eda.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "eda.md").write_text(_to_md(architecture, report), encoding="utf-8")
    return report


def _eda_snn(corpus: dict) -> dict:
    y = corpus["y"]
    names = list(SNN_CLASSES)
    counts = {names[i]: int((y == i).sum()) for i in range(len(names))}
    x = corpus.get("X_raw", corpus["X"])
    smv = None
    if x.ndim == 3 and x.shape[-1] >= 3:
        smv = np.sqrt((x[..., :3] ** 2).sum(axis=-1)).max(axis=1)
    by_class = {}
    for i, name in enumerate(names):
        mask = y == i
        if smv is not None and mask.any():
            by_class[name] = {
                "n": int(mask.sum()),
                "smv_peak_mean": float(smv[mask].mean()),
                "smv_peak_p95": float(np.quantile(smv[mask], 0.95)),
            }
        else:
            by_class[name] = {"n": int(mask.sum())}
    return {
        "source": corpus.get("source"),
        "n_windows": int(len(y)),
        "n_subjects": int(len(np.unique(corpus["subject"]))),
        "class_counts": counts,
        "imbalance_ratio": _imbalance(counts),
        "per_class": by_class,
        "notes": [
            "2 s windows on a uniform 50 Hz grid; split by subject, young/elder stratified for WEDA ids.",
            "Accel stored in g. Gyro stored in deg/s (WEDA rad/s × 180/π).",
            "fall_like requires ≥50% overlap with the annotated interval, or the trial SMV peak inside that interval.",
            "Training head is sit_stand, walk, fall_like, impact_adl. rest and not_worn are omitted.",
            "Jog, stumble, jump, hit-table, clap, collapse-sit and crouch are impact_adl, not a fall.",
            "SMV rhythm band is fit on training elders' walk. Gyro rhythm uses a fixed 30 deg/s band.",
            "A fall prediction also requires the window SMV peak to clear a floor chosen on validation.",
            "Class weights are the square root of inverse frequency.",
        ],
    }


def _imbalance(counts: dict) -> float:
    present = [v for v in counts.values() if v > 0]
    if not present:
        return 0.0
    return float(max(present) / min(present))


def _eda_sqi(corpus: dict) -> dict:
    y = corpus["y"]
    x = corpus["X"]
    names = corpus.get("feature_names") or SQI_FEATURES
    pos = int(y.sum())
    feat = {}
    for i, name in enumerate(names):
        col = x[:, i]
        feat[name] = {
            "mean_good": float(col[y == 1].mean()) if (y == 1).any() else None,
            "mean_bad": float(col[y == 0].mean()) if (y == 0).any() else None,
        }
    return {
        "source": corpus.get("source"),
        "n_windows": int(len(y)),
        "n_subjects": int(len(np.unique(corpus["subject"]))),
        "n_good": pos,
        "n_bad": int(len(y) - pos),
        "yield": float(pos / len(y)) if len(y) else 0.0,
        "features": feat,
        "notes": [
            "y=1 when |HR_ppg - HR_ref| <= 5 bpm. Do not label from the IQR rule.",
            "PPG-DaLiA has no SpO2 reference — the SpO2 gate stays rule-based.",
        ],
    }


def _eda_trend(corpus: dict) -> dict:
    y = corpus["y"]
    x = corpus["X"]
    names = TREND_FEATURES
    return {
        "source": corpus.get("source"),
        "n_windows": int(len(y)),
        "n_subjects": int(len(np.unique(corpus["subject"]))),
        "n_rise": int(y.sum()),
        "n_stable": int((y == 0).sum()),
        "positive_rate": float(y.mean()) if len(y) else 0.0,
        "l_news_now_hist": dict(Counter(x[:, -1].astype(int).tolist())),
        "feature_means": {names[i]: float(x[:, i].mean()) for i in range(min(len(names), x.shape[1]))},
        "notes": [
            "Self-label: L_news(t+2h) > L_news(t). Positive cases are usually rare.",
            "MIMIC is ICU bedside — domain shift vs a wristband; Hybrid FL is a proof of concept.",
        ],
    }


def _to_md(architecture: str, report: dict) -> str:
    lines = [f"# EDA `{architecture}`", "", f"Source: `{report.get('source')}`", ""]
    for key, value in report.items():
        if key == "notes":
            lines.append("## Notes")
            lines.extend(f"- {n}" for n in value)
            continue
        if isinstance(value, dict):
            lines.append(f"## {key}")
            lines.append("```json")
            lines.append(json.dumps(value, indent=2, ensure_ascii=False))
            lines.append("```")
        else:
            lines.append(f"- **{key}**: {value}")
    return "\n".join(lines) + "\n"
