"""NEWS2 pulse / SpO2 Scale 1 scores plus a PPG stability SQI.

HR and SpO2 come from the same optical (PPG) sensor, so they share one
validity decision. Besides the IMU motion gate, the PPG channel itself must
be stable across the acquire window: a large inter-quartile range (IQR) of
HR or SpO2 at rest indicates poor beat detection or loose probe contact.

    ppg_stable = IQR(HR) <= IQR_HR_max  and  IQR(SpO2) <= IQR_SpO2_max

Default limits are pre-calibration and must be confirmed against a
reference pulse oximeter on the target hardware.
"""

from __future__ import annotations

from dataclasses import dataclass

from algorithms.news2_subset import pulse_score, spo2_scale1_score
from algorithms.sliding_win import SessionWindow

DEFAULT_MAX_IQR_HR_BPM = 10.0
DEFAULT_MAX_IQR_SPO2_PCT = 2.0


@dataclass(frozen=True)
class PhysioNews2Result:
    """Subset NEWS2 scores for HR and SpO2 (not a disease probability)."""

    hr_bpm: float | None
    spo2_percent: float | None
    hr_score: int | None
    spo2_score: int | None
    iqr_hr: float | None
    iqr_spo2: float | None
    n_valid_hr: int
    n_valid_spo2: int
    complete: bool
    ppg_stable: bool
    ppg_reasons: tuple[str, ...]


class PhysioNews2Engine:
    """Score median HR / SpO2 with NEWS2 tables and check PPG stability."""

    def __init__(
        self,
        *,
        max_iqr_hr_bpm: float = DEFAULT_MAX_IQR_HR_BPM,
        max_iqr_spo2_pct: float = DEFAULT_MAX_IQR_SPO2_PCT,
    ) -> None:
        if max_iqr_hr_bpm <= 0 or max_iqr_spo2_pct <= 0:
            raise ValueError("PPG IQR limits must be positive")
        self.max_iqr_hr_bpm = max_iqr_hr_bpm
        self.max_iqr_spo2_pct = max_iqr_spo2_pct

    def evaluate(self, window: SessionWindow) -> PhysioNews2Result:
        hr = window.median_hr
        spo2 = window.median_spo2
        hr_score = pulse_score(hr) if hr is not None else None
        spo2_score = spo2_scale1_score(spo2) if spo2 is not None else None
        complete = hr_score is not None and spo2_score is not None

        reasons: list[str] = []
        if window.iqr_hr is None or window.iqr_hr > self.max_iqr_hr_bpm:
            reasons.append(
                f"ppg_unstable_hr_iqr:{_fmt(window.iqr_hr)}>{self.max_iqr_hr_bpm:g}"
            )
        if window.iqr_spo2 is None or window.iqr_spo2 > self.max_iqr_spo2_pct:
            reasons.append(
                f"ppg_unstable_spo2_iqr:{_fmt(window.iqr_spo2)}>{self.max_iqr_spo2_pct:g}"
            )

        return PhysioNews2Result(
            hr_bpm=hr,
            spo2_percent=spo2,
            hr_score=hr_score,
            spo2_score=spo2_score,
            iqr_hr=window.iqr_hr,
            iqr_spo2=window.iqr_spo2,
            n_valid_hr=len(window.hr_valid),
            n_valid_spo2=len(window.spo2_valid),
            complete=complete,
            ppg_stable=not reasons,
            ppg_reasons=tuple(reasons),
        )


def _fmt(value: float | None) -> str:
    return "none" if value is None else f"{value:g}"
