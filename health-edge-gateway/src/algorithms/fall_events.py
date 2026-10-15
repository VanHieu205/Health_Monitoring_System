"""Event-level fall rules on one resampled accel trial.

WEDA recordings end a few seconds after the impact, and the wrist is not
still at 0.08 g, so a 10 s inactivity test does not separate falls from ADL.
The rule used here is: one strong impact, a posture change, and few other
impacts nearby (a fall is one hit; clapping, running and hitting a table repeat).

A trial is one decision. The 15–30 s cancel window is not applied.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

FS = 50.0
PEAK_RADIUS_S = 3.0
PEAK_SEP_S = 0.3
PEAK_FLOORS_G = (1.5, 2.0, 2.5)
POSE_PRE_S = 1.0
POSE_PRE_GAP_S = 0.2
POSE_POST_GAP_S = 0.5
POSE_POST_S = 1.0
POSE_POST_LIMIT_S = 4.0
MIN_POSE_S = 0.4
TARGET_SENSITIVITY = 0.90

# Tie-break centre, from the train/val probe: 3.5 g keeps Se >= 90% for SMV
# alone, and <= 3 nearby peaks at 2 g with a 35° turn drops repeated ADL hits.
DESIGN_SMV_G = 3.5
DESIGN_POSTURE_DEG = 35.0
DESIGN_MAX_PEAKS = 3
DESIGN_PEAK_FLOOR_G = 2.0

SMV_GRID_G = (2.0, 2.5, 3.0, 3.5, 4.0, 4.5)
ISO_SMV_GRID_G = (2.5, 3.0, 3.5, 4.0)
ISO_POSTURE_GRID_DEG = (20.0, 30.0, 35.0, 45.0)
ISO_MAX_PEAKS = (2, 3, 4)
ISO_FLOOR_GRID_G = PEAK_FLOORS_G


@dataclass(frozen=True)
class TrialFeatures:
    peak_index: int
    peak_smv_g: float
    posture_deg: float | None
    post_peak_s: float
    # Peak groups within ±3 s of the main peak, one count per PEAK_FLOORS_G.
    peak_counts: tuple[int, ...]


def trial_features(acc_g: np.ndarray, *, fs: float = FS) -> TrialFeatures:
    acc = np.asarray(acc_g, dtype=np.float64)
    if acc.ndim != 2 or acc.shape[1] != 3 or len(acc) < 3:
        return TrialFeatures(0, 0.0, None, 0.0, tuple(0 for _ in PEAK_FLOORS_G))
    smv = np.sqrt((acc * acc).sum(axis=1))
    peak = int(np.argmax(smv))
    counts = tuple(_count_near(smv, peak, fs, floor) for floor in PEAK_FLOORS_G)
    return TrialFeatures(
        peak,
        float(smv[peak]),
        _posture_deg(acc, peak, fs),
        float((len(smv) - 1 - peak) / fs),
        counts,
    )


def fires_smv(features: TrialFeatures, smv_g: float) -> bool:
    return features.peak_smv_g >= smv_g


def fires_isolated(
    features: TrialFeatures,
    smv_g: float,
    posture_deg: float,
    max_peaks: int,
    peak_floor_g: float,
) -> bool:
    if features.peak_smv_g < smv_g:
        return False
    if features.posture_deg is None or features.posture_deg < posture_deg:
        return False
    return _count_at(features, peak_floor_g) <= max_peaks


def assert_event_rules() -> None:
    """One impact with a turn is a fall. Repeated peaks are not."""
    fs = FS
    n_pre, n_hit, n_lie = int(2 * fs), int(0.2 * fs), int(4 * fs)
    fall = np.zeros((n_pre + n_hit + n_lie, 3))
    fall[:n_pre, 2] = 1.0
    fall[n_pre : n_pre + n_hit, 0] = 4.0
    fall[n_pre + n_hit :, 0] = 1.0
    feat = trial_features(fall, fs=fs)
    if not fires_smv(feat, DESIGN_SMV_G):
        raise AssertionError("synthetic fall missed the SMV step")
    if not fires_isolated(feat, DESIGN_SMV_G, DESIGN_POSTURE_DEG, DESIGN_MAX_PEAKS, DESIGN_PEAK_FLOOR_G):
        raise AssertionError("synthetic fall missed the isolated-peak rule")

    t = np.arange(0.0, 12.0, 1.0 / fs)
    walk = np.zeros((len(t), 3))
    walk[:, 2] = 1.0
    walk[:, 0] = 2.4 * np.sin(2.0 * math.pi * 2.0 * t)
    walk_feat = trial_features(walk, fs=fs)
    if not fires_smv(walk_feat, 2.5):
        raise AssertionError("synthetic walk should still cross 2.5 g")
    if fires_isolated(walk_feat, 2.5, 20.0, DESIGN_MAX_PEAKS, DESIGN_PEAK_FLOOR_G):
        raise AssertionError("repeated peaks were called a fall")


def _count_at(features: TrialFeatures, floor_g: float) -> int:
    for floor, count in zip(PEAK_FLOORS_G, features.peak_counts, strict=True):
        if abs(floor - floor_g) < 1e-9:
            return count
    raise ValueError(f"peak floor {floor_g} is not in {PEAK_FLOORS_G}")


def _count_near(smv: np.ndarray, peak: int, fs: float, floor: float) -> int:
    rad = int(round(PEAK_RADIUS_S * fs))
    sep = max(1, int(round(PEAK_SEP_S * fs)))
    i0 = max(0, peak - rad)
    i1 = min(len(smv), peak + rad + 1)
    idx = np.flatnonzero(smv[i0:i1] >= floor)
    if len(idx) == 0:
        return 0
    return 1 + int(np.sum(np.diff(idx) > sep))


def _posture_deg(acc: np.ndarray, peak: int, fs: float) -> float | None:
    pre = _block(
        acc,
        int(round(peak - (POSE_PRE_GAP_S + POSE_PRE_S) * fs)),
        int(round(peak - POSE_PRE_GAP_S * fs)),
        fs,
    )
    post_end = min(
        int(round(peak + POSE_POST_LIMIT_S * fs)),
        int(round(peak + (POSE_POST_GAP_S + POSE_POST_S) * fs)),
        len(acc),
    )
    post = _block(acc, int(round(peak + POSE_POST_GAP_S * fs)), post_end, fs)
    if pre is None or post is None:
        return None
    u, v = _mean_unit(pre), _mean_unit(post)
    if u is None or v is None:
        return None
    dot = max(-1.0, min(1.0, float(np.dot(u, v))))
    return math.degrees(math.acos(dot))


def _block(acc: np.ndarray, i0: int, i1: int, fs: float) -> np.ndarray | None:
    i0 = max(0, i0)
    i1 = min(len(acc), i1)
    if i1 - i0 < int(round(MIN_POSE_S * fs)):
        return None
    return acc[i0:i1]


def _mean_unit(block: np.ndarray) -> np.ndarray | None:
    mean = block.mean(axis=0)
    norm = float(np.linalg.norm(mean))
    if norm < 1e-6:
        return None
    return mean / norm
