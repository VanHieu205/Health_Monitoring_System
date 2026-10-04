"""NEWS2 temperature component after optional sensor-to-core offset.

Kiosk thermometers are usually **skin / IR**, not core. Estimated core is

    T_core,est = T_sensor + δ

where ``δ`` must come from a calibration protocol against a reference
thermometer (Bland–Altman). Default ``δ = 0`` means “treat the stored
value as already core-equivalent” — do **not** invent a normal
temperature when the column is missing.

Scores follow Royal College of Physicians NEWS2 (2017) temperature
cut-points after rounding to 0.1 °C. This is not a probability of fever.
"""

from __future__ import annotations

from dataclasses import dataclass

from algorithms.news2_subset import temperature_score
from algorithms.sliding_win import SessionWindow


@dataclass(frozen=True)
class TemperatureNews2Result:
    """NEWS2 temperature score or an explicit missing component."""

    t_sensor_c: float | None
    t_core_est_c: float | None
    offset_c: float
    news2_score: int | None
    missing: bool
    n_valid: int


class TemperatureRuleEngine:
    """Map median acquire temperature onto the NEWS2 temperature table."""

    def __init__(self, *, core_offset_c: float = 0.0) -> None:
        self.core_offset_c = float(core_offset_c)

    def evaluate(self, window: SessionWindow) -> TemperatureNews2Result:
        t_sensor = window.median_temp
        if t_sensor is None:
            return TemperatureNews2Result(
                t_sensor_c=None,
                t_core_est_c=None,
                offset_c=self.core_offset_c,
                news2_score=None,
                missing=True,
                n_valid=0,
            )
        t_core = t_sensor + self.core_offset_c
        return TemperatureNews2Result(
            t_sensor_c=t_sensor,
            t_core_est_c=t_core,
            offset_c=self.core_offset_c,
            news2_score=temperature_score(t_core),
            missing=False,
            n_valid=len(window.temp_valid),
        )
