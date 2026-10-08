"""Technical SQI for the fall IMU channel (not a rest/motion gate).

A fall *must* contain large acceleration. The PPG rest gate
(``motion_gate.MotionQualityGate``) therefore must not be reused here.

This gate only asks whether the IMU stream is usable: enough samples,
not ADC-saturated, watch likely worn. It does not classify falls.
"""

from __future__ import annotations

from dataclasses import dataclass

from algorithms.sliding_win import SessionWindow

DEFAULT_MIN_SAMPLES = 15
# MPU6050 int16 saturates at ±32768 LSB.
DEFAULT_SATURATION_LSB = 32000
DEFAULT_MAX_SATURATED_FRACTION = 0.2


@dataclass(frozen=True)
class ImuFallGateResult:
    passed: bool
    n_samples: int
    saturated_fraction: float
    reason: str


class ImuFallQualityGate:
    """Fail-closed technical check before the fall pipeline."""

    def __init__(
        self,
        *,
        min_samples: int = DEFAULT_MIN_SAMPLES,
        saturation_lsb: float = DEFAULT_SATURATION_LSB,
        max_saturated_fraction: float = DEFAULT_MAX_SATURATED_FRACTION,
    ) -> None:
        if min_samples < 1:
            raise ValueError("min_samples must be >= 1")
        self.min_samples = min_samples
        self.saturation_lsb = saturation_lsb
        self.max_saturated_fraction = max_saturated_fraction

    def evaluate(self, window: SessionWindow) -> ImuFallGateResult:
        n = len(window.acc_x)
        if n < self.min_samples:
            return ImuFallGateResult(
                passed=False,
                n_samples=n,
                saturated_fraction=0.0,
                reason="insufficient_imu_samples",
            )
        saturated = 0
        for x, y, z in zip(window.acc_x, window.acc_y, window.acc_z, strict=True):
            if (
                abs(x) >= self.saturation_lsb
                or abs(y) >= self.saturation_lsb
                or abs(z) >= self.saturation_lsb
            ):
                saturated += 1
        frac = saturated / n
        if frac > self.max_saturated_fraction:
            return ImuFallGateResult(
                passed=False,
                n_samples=n,
                saturated_fraction=frac,
                reason=f"imu_adc_saturated:{frac:.2f}",
            )
        return ImuFallGateResult(
            passed=True,
            n_samples=n,
            saturated_fraction=frac,
            reason="imu_fall_sqi_pass",
        )
