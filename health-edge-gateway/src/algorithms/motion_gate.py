"""IMU signal-quality index (SQI) for the kiosk acquire window.

PPG-derived HR/SpO2 is not trustworthy under motion artefact. This gate
does **not** estimate disease risk.

Method
------
1. Convert MPU-6050 LSBs to g using the configured full-scale sensitivity
   (default ±2 g → 16384 LSB/g; must match firmware).
2. Remove the nearly-constant gravity/bias term by subtracting the
   per-axis mean over the acquire window (valid when the subject is
   seated and orientation is stable):

       a_dyn(t) = a(t) − mean(a)

3. RMS of the dynamic vector:

       RMS = sqrt( mean( ||a_dyn||^2 ) )   [g]

4. Map RMS to {pass, marginal, fail} with **device-calibration
   thresholds** (defaults below are pre-calibration only).

Fail-closed: only ``pass`` may proceed to vital scoring. ``marginal``
means remasure, not “lower the clinical score”.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from algorithms.sliding_win import SessionWindow

MPU6050_LSB_PER_G = 16384.0
# Pre-calibration defaults (replace after seated vs fidget ROC on-device).
DEFAULT_RMS_PASS_G = 0.05
DEFAULT_RMS_FAIL_G = 0.12
DEFAULT_MIN_SAMPLES = 30


class SqiLevel(str, Enum):
    PASS = "pass"
    MARGINAL = "marginal"
    FAIL = "fail"


@dataclass(frozen=True)
class MotionGateResult:
    """SQI for one acquire window."""

    level: SqiLevel
    passed: bool
    rms_dyn_g: float | None
    n_samples: int
    reason: str
    rms_pass_g: float
    rms_fail_g: float


class MotionQualityGate:
    """Classify rest vs motion from RMS dynamic acceleration."""

    def __init__(
        self,
        *,
        rms_pass_g: float = DEFAULT_RMS_PASS_G,
        rms_fail_g: float = DEFAULT_RMS_FAIL_G,
        lsb_per_g: float = MPU6050_LSB_PER_G,
        min_samples: int = DEFAULT_MIN_SAMPLES,
    ) -> None:
        if rms_pass_g <= 0 or rms_fail_g <= rms_pass_g:
            raise ValueError("require 0 < rms_pass_g < rms_fail_g")
        if lsb_per_g <= 0:
            raise ValueError("lsb_per_g must be positive")
        self.rms_pass_g = rms_pass_g
        self.rms_fail_g = rms_fail_g
        self.lsb_per_g = lsb_per_g
        self.min_samples = min_samples

    def evaluate(self, window: SessionWindow) -> MotionGateResult:
        n = len(window.acc_x)
        if n < self.min_samples:
            return MotionGateResult(
                level=SqiLevel.FAIL,
                passed=False,
                rms_dyn_g=None,
                n_samples=n,
                reason="insufficient_samples",
                rms_pass_g=self.rms_pass_g,
                rms_fail_g=self.rms_fail_g,
            )
        ax = [v / self.lsb_per_g for v in window.acc_x]
        ay = [v / self.lsb_per_g for v in window.acc_y]
        az = [v / self.lsb_per_g for v in window.acc_z]
        mx, my, mz = _mean(ax), _mean(ay), _mean(az)
        energy = 0.0
        for x, y, z in zip(ax, ay, az, strict=True):
            dx, dy, dz = x - mx, y - my, z - mz
            energy += dx * dx + dy * dy + dz * dz
        rms = math.sqrt(energy / n)
        level, reason = self._classify(rms)
        return MotionGateResult(
            level=level,
            passed=level is SqiLevel.PASS,
            rms_dyn_g=rms,
            n_samples=n,
            reason=reason,
            rms_pass_g=self.rms_pass_g,
            rms_fail_g=self.rms_fail_g,
        )

    def _classify(self, rms: float) -> tuple[SqiLevel, str]:
        if rms < self.rms_pass_g:
            return SqiLevel.PASS, "sqi_pass"
        if rms < self.rms_fail_g:
            return SqiLevel.MARGINAL, "sqi_marginal_remeasure"
        return SqiLevel.FAIL, "sqi_fail_motion"


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)
