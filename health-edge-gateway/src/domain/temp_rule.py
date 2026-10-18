"""NEWS2 temperature component with its own quality check.

Kiosk thermometers are usually **skin / IR**, not core. Estimated core is

    T_core,est = T_sensor + δ

where ``δ`` must come from a calibration protocol against a reference
thermometer (Bland–Altman). Default ``δ = 0`` means “treat the stored
value as already core-equivalent” — do **not** invent a normal
temperature when the column is missing.

The temperature channel is validated independently of the IMU (motion
corrupts PPG, not a thermometer):

    valid = n_valid >= N_min  and  IQR(T) <= IQR_T_max

Scores follow Royal College of Physicians NEWS2 (2017) temperature
cut-points after rounding to 0.1 °C. This is not a probability of fever.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.news2_subset import temperature_score
from domain.sliding_win import SessionWindow

DEFAULT_MIN_TEMP_SAMPLES = 10
DEFAULT_MAX_IQR_TEMP_C = 0.3

TEMP_VALID = "valid"
TEMP_MISSING = "missing"
TEMP_INSUFFICIENT = "insufficient_samples"
TEMP_UNSTABLE = "unstable"


@dataclass(frozen=True)
class TemperatureNews2Result:
    """NEWS2 temperature score with an explicit channel status."""

    t_sensor_c: float | None
    t_core_est_c: float | None
    offset_c: float
    news2_score: int | None
    status: str
    iqr_c: float | None
    n_valid: int

    @property
    def missing(self) -> bool:
        return self.status == TEMP_MISSING

    @property
    def valid(self) -> bool:
        return self.status == TEMP_VALID


class TemperatureRuleEngine:
    """Map median acquire temperature onto the NEWS2 temperature table."""

    def __init__(
        self,
        *,
        core_offset_c: float = 0.0,
        min_samples: int = DEFAULT_MIN_TEMP_SAMPLES,
        max_iqr_c: float = DEFAULT_MAX_IQR_TEMP_C,
    ) -> None:
        if min_samples < 1 or max_iqr_c <= 0:
            raise ValueError("min_samples >= 1 and max_iqr_c > 0 required")
        self.core_offset_c = float(core_offset_c)
        self.min_samples = min_samples
        self.max_iqr_c = max_iqr_c

    def evaluate(self, window: SessionWindow) -> TemperatureNews2Result:
        n_valid = len(window.temp_valid)
        t_sensor = window.median_temp
        if t_sensor is None:
            return self._result(None, TEMP_MISSING, window.iqr_temp, n_valid)
        if n_valid < self.min_samples:
            return self._result(t_sensor, TEMP_INSUFFICIENT, window.iqr_temp, n_valid)
        if window.iqr_temp is not None and window.iqr_temp > self.max_iqr_c:
            return self._result(t_sensor, TEMP_UNSTABLE, window.iqr_temp, n_valid)
        return self._result(t_sensor, TEMP_VALID, window.iqr_temp, n_valid)

    def _result(
        self,
        t_sensor: float | None,
        status: str,
        iqr_c: float | None,
        n_valid: int,
    ) -> TemperatureNews2Result:
        t_core = None if t_sensor is None else t_sensor + self.core_offset_c
        score = temperature_score(t_core) if status == TEMP_VALID and t_core is not None else None
        return TemperatureNews2Result(
            t_sensor_c=t_sensor,
            t_core_est_c=t_core,
            offset_c=self.core_offset_c,
            news2_score=score,
            status=status,
            iqr_c=iqr_c,
            n_valid=n_valid,
        )
