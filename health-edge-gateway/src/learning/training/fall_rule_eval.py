"""FR-01 / FR-02 on whole WEDA trials.

Rule thresholds are chosen without the subject being scored. LOSO does this
once per person. The SNN may only raise a possible fall to a fall, and its
threshold is chosen on the validation subjects of the seed-42 split.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from domain.fall_events import (
    DESIGN_MAX_PEAKS,
    DESIGN_PEAK_FLOOR_G,
    DESIGN_POSTURE_DEG,
    DESIGN_SMV_G,
    ISO_FLOOR_GRID_G,
    ISO_MAX_PEAKS,
    ISO_POSTURE_GRID_DEG,
    ISO_SMV_GRID_G,
    SMV_GRID_G,
    TARGET_SENSITIVITY,
    TrialFeatures,
    fires_isolated,
    fires_smv,
    trial_features,
)
from learning.training.data.prepare.weda import WedaTrial
from learning.training.metrics import wilson_interval
from learning.training.preprocess import subject_holdout

WIN = 100


@dataclass(frozen=True)
class ScoredTrial:
    code: str
    subject: str
    rep: str
    is_fall: bool
    duration_s: float
    features: TrialFeatures
    imu: np.ndarray


@dataclass(frozen=True)
class RuleSpec:
    name: str
    smv_g: float
    posture_deg: float | None = None
    max_peaks: int | None = None
    peak_floor_g: float | None = None

    def fires(self, trial: ScoredTrial) -> bool:
        if self.posture_deg is None or self.max_peaks is None or self.peak_floor_g is None:
            return fires_smv(trial.features, self.smv_g)
        return fires_isolated(
            trial.features,
            self.smv_g,
            self.posture_deg,
            self.max_peaks,
            self.peak_floor_g,
        )

    def as_dict(self) -> dict:
        out = {"name": self.name, "smv_g": self.smv_g}
        if self.posture_deg is not None:
            out["posture_deg"] = self.posture_deg
            out["max_peaks"] = self.max_peaks
            out["peak_floor_g"] = self.peak_floor_g
        return out


def score_trials(trials: list[WedaTrial]) -> list[ScoredTrial]:
    scored: list[ScoredTrial] = []
    for trial in trials:
        scored.append(
            ScoredTrial(
                code=trial.code,
                subject=trial.subject,
                rep=trial.rep,
                is_fall=trial.is_fall,
                duration_s=trial.duration_s,
                features=trial_features(trial.acc_g),
                imu=trial.imu,
            )
        )
    return scored


def split_subjects(subjects: list[str], *, seed: int) -> dict[str, list[str]]:
    """Same subject holdout as SNN training (one row per subject, same seed)."""
    names = np.unique(np.asarray(subjects, dtype=str))
    corpus = {
        "X": np.zeros((len(names), 1), dtype=np.float32),
        "y": np.zeros(len(names), dtype=np.int64),
        "subject": names,
    }
    split = subject_holdout(corpus, seed=seed)

    def uniq(arr: np.ndarray) -> list[str]:
        return sorted({str(s) for s in arr})

    return {
        "train": uniq(split.subject_train),
        "val": uniq(split.subject_val),
        "test": uniq(split.subject_test),
    }


def select_rules(trials: list[ScoredTrial]) -> tuple[RuleSpec, RuleSpec]:
    """Pick SMV-only and isolated-peak points. ``trials`` must exclude the test subject."""
    smv = _best((RuleSpec("smv_only", smv_g) for smv_g in SMV_GRID_G), trials)
    isolated = _best(
        (
            RuleSpec("isolated_peak", smv_g, deg, peaks, floor)
            for smv_g in ISO_SMV_GRID_G
            for deg in ISO_POSTURE_GRID_DEG
            for peaks in ISO_MAX_PEAKS
            for floor in ISO_FLOOR_GRID_G
        ),
        trials,
    )
    return smv, isolated


def evaluate_split(
    trials: list[ScoredTrial],
    rule: RuleSpec,
    *,
    scores: np.ndarray | None = None,
    snn_tau: float | None = None,
) -> dict:
    """Count one decision per trial.

    When ``scores`` and ``snn_tau`` are set, a trial the rule misses is still
    a fall if its SMV clears the rule threshold and the SNN score clears tau.
    The SNN cannot clear a fall the rule already accepted.
    """
    detected = [_detect(t, rule, i, scores, snn_tau) for i, t in enumerate(trials)]
    falls = [(t, hit) for t, hit in zip(trials, detected, strict=True) if t.is_fall]
    adl = [(t, hit) for t, hit in zip(trials, detected, strict=True) if not t.is_fall]
    hit = sum(1 for _, flag in falls if flag)
    n_fa = sum(1 for _, flag in adl if flag)
    n_fall = len(falls)
    n_adl = len(adl)
    by_subject: dict[str, dict] = {}
    for trial, flag in zip(trials, detected, strict=True):
        row = by_subject.setdefault(
            trial.subject,
            {"n_fall": 0, "n_fall_detected": 0, "n_adl": 0, "n_false_alarms": 0, "adl_hours": 0.0},
        )
        if trial.is_fall:
            row["n_fall"] += 1
            row["n_fall_detected"] += int(flag)
        else:
            row["n_adl"] += 1
            row["adl_hours"] += trial.duration_s / 3600.0
            row["n_false_alarms"] += int(flag)
    rates = []
    for row in by_subject.values():
        if row["adl_hours"] > 0:
            row["far_per_day"] = row["n_false_alarms"] / row["adl_hours"] * 24.0
            rates.append(row["far_per_day"])
        else:
            row["far_per_day"] = None
    adl_hours = sum(t.duration_s for t, _ in adl) / 3600.0
    ci = wilson_interval(hit, n_fall)
    return {
        "n_fall": n_fall,
        "n_fall_detected": hit,
        "sensitivity": (hit / n_fall) if n_fall else None,
        "sensitivity_ci95": list(ci) if ci else None,
        "n_adl": n_adl,
        "n_false_alarms": n_fa,
        "false_alarms_per_adl_trial": (n_fa / n_adl) if n_adl else None,
        "specificity": ((n_adl - n_fa) / n_adl) if n_adl else None,
        "adl_hours": adl_hours,
        "far_per_resident_day": (sum(rates) / len(rates)) if rates else None,
        "far_per_day_note": (
            "Extrapolated from scripted WEDA clips, not a free-living day. "
            "The cancel window is not applied."
        ),
        "per_subject": {k: by_subject[k] for k in sorted(by_subject)},
    }


def run_loso(trials: list[ScoredTrial]) -> dict:
    """One fold per subject. Thresholds for a fold never see that subject."""
    subjects = sorted({t.subject for t in trials})
    folds = []
    for subject in subjects:
        test = [t for t in trials if t.subject == subject]
        pool = [t for t in trials if t.subject != subject]
        smv, isolated = select_rules(pool)
        folds.append(
            {
                "subject": subject,
                "smv_only": _fold_row(smv, test),
                "isolated_peak": _fold_row(isolated, test),
            }
        )
    return {
        "protocol": "leave_one_subject_out",
        "n_subjects": len(subjects),
        "smv_only": _pool(folds, "smv_only"),
        "isolated_peak": _pool(folds, "isolated_peak"),
    }


def peak_windows(trials: list[ScoredTrial], win: int = WIN) -> np.ndarray:
    """100-sample window centred on each trial's SMV peak. Shape (N, 100, 6)."""
    out = np.zeros((len(trials), win, 6), dtype=np.float32)
    for i, trial in enumerate(trials):
        imu = np.asarray(trial.imu, dtype=np.float32)
        peak = int(trial.features.peak_index)
        start = peak - win // 2
        src0 = max(0, start)
        dst0 = max(0, -start)
        n = min(win - dst0, len(imu) - src0)
        if n > 0:
            out[i, dst0 : dst0 + n] = imu[src0 : src0 + n]
        if dst0 > 0:
            out[i, :dst0] = out[i, dst0]
        end = dst0 + max(n, 0)
        if 0 < end < win:
            out[i, end:] = out[i, end - 1]
    return out


def choose_snn_tau(
    trials: list[ScoredTrial],
    rule: RuleSpec,
    scores: np.ndarray,
) -> float:
    """Val-only operating point. SNN may only add falls the rule missed."""
    best_tau, best_key = 0.5, None
    for tau in np.linspace(0.05, 0.95, 37):
        metrics = evaluate_split(trials, rule, scores=scores, snn_tau=float(tau))
        key = _rank_metrics(metrics, distance=abs(float(tau) - 0.5))
        if best_key is None or key > best_key:
            best_tau, best_key = float(tau), key
    return best_tau


def _detect(
    trial: ScoredTrial,
    rule: RuleSpec,
    index: int,
    scores: np.ndarray | None,
    snn_tau: float | None,
) -> bool:
    if rule.fires(trial):
        return True
    if scores is None or snn_tau is None:
        return False
    if trial.features.peak_smv_g < rule.smv_g:
        return False
    return bool(scores[index] >= snn_tau)


def _fold_row(rule: RuleSpec, test: list[ScoredTrial]) -> dict:
    metrics = evaluate_split(test, rule)
    metrics.pop("per_subject", None)
    metrics.pop("far_per_day_note", None)
    return {"thresholds": rule.as_dict(), **metrics}


def _pool(folds: list[dict], key: str) -> dict:
    rows = [fold[key] for fold in folds]
    n_fall = sum(r["n_fall"] for r in rows)
    hit = sum(r["n_fall_detected"] for r in rows)
    n_adl = sum(r["n_adl"] for r in rows)
    n_fa = sum(r["n_false_alarms"] for r in rows)
    rates = [r["far_per_resident_day"] for r in rows if r["far_per_resident_day"] is not None]
    ci = wilson_interval(hit, n_fall)
    thresholds = [r["thresholds"] for r in rows]
    return {
        "n_fall": n_fall,
        "n_fall_detected": hit,
        "sensitivity": (hit / n_fall) if n_fall else None,
        "sensitivity_ci95": list(ci) if ci else None,
        "n_adl": n_adl,
        "n_false_alarms": n_fa,
        "false_alarms_per_adl_trial": (n_fa / n_adl) if n_adl else None,
        "specificity": ((n_adl - n_fa) / n_adl) if n_adl else None,
        "far_per_resident_day_mean": (sum(rates) / len(rates)) if rates else None,
        "threshold_median": _median_thresholds(thresholds),
        "folds": rows,
    }


def _median_thresholds(rows: list[dict]) -> dict:
    smv = sorted(r["smv_g"] for r in rows)
    mid = smv[len(smv) // 2]
    out = {"smv_g": mid}
    if "posture_deg" in rows[0]:
        out["posture_deg"] = sorted(r["posture_deg"] for r in rows)[len(rows) // 2]
        out["max_peaks"] = sorted(r["max_peaks"] for r in rows)[len(rows) // 2]
        out["peak_floor_g"] = sorted(r["peak_floor_g"] for r in rows)[len(rows) // 2]
    return out


def _best(rules, trials: list[ScoredTrial]) -> RuleSpec:
    chosen: RuleSpec | None = None
    chosen_key: tuple | None = None
    for rule in rules:
        key = _rank_metrics(evaluate_split(trials, rule), _distance(rule))
        if chosen_key is None or key > chosen_key:
            chosen, chosen_key = rule, key
    if chosen is None:
        raise RuntimeError("empty threshold grid")
    return chosen


def _rank_metrics(metrics: dict, distance: float) -> tuple:
    se = metrics["sensitivity"]
    se = -1.0 if se is None else float(se)
    fa = metrics["false_alarms_per_adl_trial"]
    fa = 1.0 if fa is None else float(fa)
    meets = 1 if se + 1e-12 >= TARGET_SENSITIVITY else 0
    primary = -fa if meets else se
    return (meets, primary, -fa, se, -distance)


def _distance(rule: RuleSpec) -> float:
    dist = abs(rule.smv_g - DESIGN_SMV_G) / DESIGN_SMV_G
    if rule.posture_deg is not None:
        dist += abs(rule.posture_deg - DESIGN_POSTURE_DEG) / DESIGN_POSTURE_DEG
    if rule.max_peaks is not None:
        dist += abs(rule.max_peaks - DESIGN_MAX_PEAKS) / DESIGN_MAX_PEAKS
    if rule.peak_floor_g is not None:
        dist += abs(rule.peak_floor_g - DESIGN_PEAK_FLOOR_G) / DESIGN_PEAK_FLOOR_G
    return dist
