"""Map a valid NEWS2 subset onto a vitals *decision* (not a disease probability)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.physio_rule import PhysioNews2Result
from domain.ppg_sqi import PpgSqiResult
from domain.temp_rule import TemperatureNews2Result

DEFAULT_REVIEW_SUM = 5
N_CHANNELS = 3


class VitalsDecision(str, Enum):
    INVALID = "vitals_invalid"
    OK = "vitals_ok"
    WATCH = "vitals_watch"
    URGENT = "vitals_urgent"


@dataclass(frozen=True)
class VitalsBranchResult:
    decision: VitalsDecision
    subset_total: int | None
    max_component: int | None
    completeness: float
    n_components: int
    max_subset: int | None
    hr_score: int | None
    spo2_score: int | None
    temp_score: int | None
    reasons: tuple[str, ...]
    warning: str


class VitalsBranch:
    def __init__(
        self,
        *,
        require_temperature: bool = False,
        review_sum: int = DEFAULT_REVIEW_SUM,
    ) -> None:
        if review_sum < 1:
            raise ValueError("review_sum must be >= 1")
        self.require_temperature = require_temperature
        self.review_sum = review_sum

    def evaluate(
        self,
        *,
        sqi: PpgSqiResult,
        physio: PhysioNews2Result,
        temperature: TemperatureNews2Result,
    ) -> VitalsBranchResult:
        if not sqi.passed:
            return VitalsBranchResult(
                decision=VitalsDecision.INVALID,
                subset_total=None,
                max_component=None,
                completeness=0.0,
                n_components=0,
                max_subset=None,
                hr_score=physio.hr_score,
                spo2_score=physio.spo2_score,
                temp_score=temperature.news2_score,
                reasons=sqi.reasons,
                warning="no_clinical_index_fail_closed",
            )
        reasons: list[str] = []
        if not temperature.valid:
            if self.require_temperature:
                return VitalsBranchResult(
                    decision=VitalsDecision.INVALID,
                    subset_total=None,
                    max_component=None,
                    completeness=0.0,
                    n_components=0,
                    max_subset=None,
                    hr_score=physio.hr_score,
                    spo2_score=physio.spo2_score,
                    temp_score=temperature.news2_score,
                    reasons=(f"temperature_required:{temperature.status}",),
                    warning="no_clinical_index_fail_closed",
                )
            reasons.append(f"temperature_omitted:{temperature.status}")

        assert physio.hr_score is not None and physio.spo2_score is not None
        components = [physio.hr_score, physio.spo2_score]
        temp_score: int | None = None
        if temperature.valid and temperature.news2_score is not None:
            temp_score = temperature.news2_score
            components.append(temp_score)
        s_sum = int(sum(components))
        s_max = int(max(components))
        n = len(components)
        if s_max >= 3 or s_sum >= self.review_sum:
            decision = VitalsDecision.URGENT
        elif s_max >= 1:
            decision = VitalsDecision.WATCH
        else:
            decision = VitalsDecision.OK
        return VitalsBranchResult(
            decision=decision,
            subset_total=s_sum,
            max_component=s_max,
            completeness=round(n / N_CHANNELS, 3),
            n_components=n,
            max_subset=3 * n,
            hr_score=physio.hr_score,
            spo2_score=physio.spo2_score,
            temp_score=temp_score,
            reasons=tuple(reasons),
            warning="subset_not_full_NEWS2_alert_is_local_policy",
        )
