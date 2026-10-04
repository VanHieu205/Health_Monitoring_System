"""NEWS2 Scale-1 pulse and SpO2 scores from robust session medians."""

from __future__ import annotations

from dataclasses import dataclass

from algorithms.news2_subset import pulse_score, spo2_scale1_score
from algorithms.sliding_win import SessionWindow


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


class PhysioNews2Engine:
    """Score median HR / SpO2 with published NEWS2 tables."""

    def evaluate(self, window: SessionWindow) -> PhysioNews2Result:
        hr = window.median_hr
        spo2 = window.median_spo2
        hr_score = pulse_score(hr) if hr is not None else None
        spo2_score = spo2_scale1_score(spo2) if spo2 is not None else None
        complete = hr_score is not None and spo2_score is not None
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
        )
