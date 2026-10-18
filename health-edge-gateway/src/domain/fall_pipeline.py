"""Rule-first wrist fall check. A classifier may only raise a possible fall.

Impact, posture change, and an isolated peak decide the rule. A published
model label may turn possible_fall into fall. It cannot override an
unreliable IMU sample, and it cannot clear a fall the rule already accepted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Sequence

from domain.imu_fall_gate import ImuFallGateResult
from domain.motion_gate import MPU6050_LSB_PER_G
from domain.sliding_win import SessionWindow

# LOSO median on WEDA: 3.0 g, 30°, at most 3 peaks at or above 2.5 g.
DEFAULT_SMV_IMPACT_G = 3.0
DEFAULT_POSTURE_DEG = 30.0
DEFAULT_INACTIVITY_RMS_G = 0.08
DEFAULT_INACTIVITY_TAIL = 0.4
# WEDA cannot host a 10 s stillness test. A fall is one impact plus a turn;
# repeated impacts (clap, run, hit) are rejected. Defaults match the
# event-level tie-break in domain.fall_events.
DEFAULT_MAX_PEAKS = 3
DEFAULT_PEAK_FLOOR_G = 2.5


class FallDecision(str, Enum):
    NOT_FALL = "not_fall"
    POSSIBLE_FALL = "possible_fall"
    FALL = "fall"
    CANCELLED = "cancelled"
    IMU_UNRELIABLE = "imu_unreliable"


TinyMlFn = Callable[[Sequence[float]], str | None]


@dataclass(frozen=True)
class FallPipelineResult:
    decision: FallDecision
    watch_candidate: bool
    smv_peak_g: float | None
    gravity_delta_deg: float | None
    rms_post_g: float | None
    impact: bool
    posture_changed: bool
    inactive_after: bool
    tinyml_label: str | None
    reasons: tuple[str, ...]


class FallPipeline:
    """Deterministic 3-step rules plus an optional escalate-only classifier."""

    def __init__(
        self,
        *,
        lsb_per_g: float = MPU6050_LSB_PER_G,
        smv_impact_g: float = DEFAULT_SMV_IMPACT_G,
        posture_deg: float = DEFAULT_POSTURE_DEG,
        inactivity_rms_g: float = DEFAULT_INACTIVITY_RMS_G,
        max_peaks: int = DEFAULT_MAX_PEAKS,
        peak_floor_g: float = DEFAULT_PEAK_FLOOR_G,
        tinyml: TinyMlFn | None = None,
    ) -> None:
        if lsb_per_g <= 0 or smv_impact_g <= 0:
            raise ValueError("lsb_per_g and smv_impact_g must be positive")
        self.lsb_per_g = lsb_per_g
        self.smv_impact_g = smv_impact_g
        self.posture_deg = posture_deg
        self.inactivity_rms_g = inactivity_rms_g
        self.max_peaks = max_peaks
        self.peak_floor_g = peak_floor_g
        self.tinyml = tinyml

    def evaluate(
        self,
        window: SessionWindow,
        imu_gate: ImuFallGateResult,
        *,
        cancelled: bool = False,
    ) -> FallPipelineResult:
        if not imu_gate.passed:
            return FallPipelineResult(
                decision=FallDecision.IMU_UNRELIABLE,
                watch_candidate=window.watch_fall_candidate,
                smv_peak_g=None,
                gravity_delta_deg=None,
                rms_post_g=None,
                impact=False,
                posture_changed=False,
                inactive_after=False,
                tinyml_label=None,
                reasons=(imu_gate.reason,),
            )
        if cancelled:
            return FallPipelineResult(
                decision=FallDecision.CANCELLED,
                watch_candidate=window.watch_fall_candidate,
                smv_peak_g=None,
                gravity_delta_deg=None,
                rms_post_g=None,
                impact=False,
                posture_changed=False,
                inactive_after=False,
                tinyml_label=None,
                reasons=("watch_cancel",),
            )

        ax = [v / self.lsb_per_g for v in window.acc_x]
        ay = [v / self.lsb_per_g for v in window.acc_y]
        az = [v / self.lsb_per_g for v in window.acc_z]
        smv = [math.sqrt(x * x + y * y + z * z) for x, y, z in zip(ax, ay, az, strict=True)]
        peak = max(smv) if smv else 0.0
        peak_i = smv.index(peak) if smv else 0
        impact = peak >= self.smv_impact_g or window.watch_fall_candidate
        angle = _gravity_delta_deg(ax, ay, az)
        posture = angle is not None and angle >= self.posture_deg
        groups = _impact_groups(smv, self.peak_floor_g)
        isolated = posture and 1 <= groups <= self.max_peaks
        rms_post = _rms_dynamic_tail(ax, ay, az, peak_i)
        inactive = rms_post is not None and rms_post <= self.inactivity_rms_g

        reasons: list[str] = []
        if window.watch_fall_candidate:
            reasons.append("watch_event_flag_fall")
        if peak >= self.smv_impact_g:
            reasons.append(f"smv_peak:{peak:.2f}g")
        if posture:
            reasons.append(f"posture_delta:{angle:.1f}deg")
        if isolated:
            reasons.append(f"isolated_peaks:{groups}")
        if inactive:
            reasons.append(f"inactivity_rms:{rms_post:.3f}g")

        tinyml_label = None
        if self.tinyml is not None and impact:
            features = (
                peak,
                angle if angle is not None else 0.0,
                rms_post if rms_post is not None else 1.0,
                1.0 if window.watch_fall_candidate else 0.0,
            )
            tinyml_label = self.tinyml(features)
            if tinyml_label:
                reasons.append(f"tinyml:{tinyml_label}")

        # Isolated impact confirms a fall. A watch candidate still needs the
        # short-window stillness check, because the watch already ran its own detector.
        if impact and isolated:
            decision = FallDecision.FALL
        elif impact and window.watch_fall_candidate and inactive:
            decision = FallDecision.FALL
        elif impact:
            decision = FallDecision.POSSIBLE_FALL
        else:
            decision = FallDecision.NOT_FALL

        if tinyml_label == "fall" and decision is FallDecision.POSSIBLE_FALL:
            decision = FallDecision.FALL
            reasons.append("tinyml_escalated")

        return FallPipelineResult(
            decision=decision,
            watch_candidate=window.watch_fall_candidate,
            smv_peak_g=peak,
            gravity_delta_deg=angle,
            rms_post_g=rms_post,
            impact=impact,
            posture_changed=posture,
            inactive_after=inactive,
            tinyml_label=tinyml_label,
            reasons=tuple(reasons) if reasons else ("no_impact",),
        )


def _gravity_delta_deg(
    ax: Sequence[float], ay: Sequence[float], az: Sequence[float]
) -> float | None:
    n = len(ax)
    if n < 8:
        return None
    k = max(2, n // 4)

    def mean_unit(xs: Sequence[float], ys: Sequence[float], zs: Sequence[float]) -> tuple[float, float, float]:
        mx, my, mz = sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs)
        norm = math.sqrt(mx * mx + my * my + mz * mz) or 1.0
        return mx / norm, my / norm, mz / norm

    u = mean_unit(ax[:k], ay[:k], az[:k])
    v = mean_unit(ax[-k:], ay[-k:], az[-k:])
    dot = max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1] + u[2] * v[2]))
    return math.degrees(math.acos(dot))


def _rms_dynamic_tail(
    ax: Sequence[float],
    ay: Sequence[float],
    az: Sequence[float],
    peak_i: int,
) -> float | None:
    start = min(len(ax) - 1, max(peak_i + 1, int(len(ax) * (1.0 - DEFAULT_INACTIVITY_TAIL))))
    tail_x, tail_y, tail_z = ax[start:], ay[start:], az[start:]
    n = len(tail_x)
    if n < 3:
        return None
    mx, my, mz = sum(tail_x) / n, sum(tail_y) / n, sum(tail_z) / n
    energy = 0.0
    for x, y, z in zip(tail_x, tail_y, tail_z, strict=True):
        dx, dy, dz = x - mx, y - my, z - mz
        energy += dx * dx + dy * dy + dz * dz
    return math.sqrt(energy / n)


def _impact_groups(smv: Sequence[float], floor: float) -> int:
    """Count separated runs of samples at or above ``floor``."""
    groups = 0
    active = False
    for value in smv:
        if value >= floor:
            if not active:
                groups += 1
                active = True
        else:
            active = False
    return groups
