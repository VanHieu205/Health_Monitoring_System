"""Fail-closed late fusion: SQI first, then NEWS2 subset sum.

Clinical interpretation
-----------------------
Motion SQI is a **measurement validity** flag, not a risk weight. If the
acquire window is not ``pass``, this module **abstains** (no total).

When SQI passes and the kiosk protocol is complete, the index is the
**sum of NEWS2 points** for available vitals:

    subset_total = pulse + SpO2_Scale1 [+ temperature]

This is **not** full NEWS2 and **must not** use NEWS2 escalation bands
(low / medium / high), which assume RR, BP, ACVPU and oxygen.

TinyML is intentionally **not** mixed into ``subset_total``. An optional
uncalibrated stub may be attached by the worker for research only.
"""

from __future__ import annotations

from dataclasses import dataclass

from algorithms.motion_gate import MotionGateResult, SqiLevel
from algorithms.news2_subset import ALGORITHM_VERSION, NEWS2_MAX_PER_VITAL
from algorithms.physio_rule import PhysioNews2Result
from algorithms.sliding_win import SessionWindow
from algorithms.temp_rule import TemperatureNews2Result

STATUS_SCORED = "scored"
STATUS_INVALID = "invalid_measurement"
STATUS_INCOMPLETE = "incomplete_protocol"


@dataclass(frozen=True)
class FusionResult:
    """Session decision: scored subset or explicit abstain."""

    status: str
    algorithm_version: str
    subset_total: int | None
    max_subset: int | None
    n_components: int
    hr_score: int | None
    spo2_score: int | None
    temp_score: int | None
    sqi_level: str
    motion_passed: bool
    reasons: tuple[str, ...]
    warning: str


class DecisionFusion:
    """Abstain unless protocol + SQI pass; then add NEWS2 subset points."""

    def __init__(self, *, require_temperature: bool = False) -> None:
        self.require_temperature = require_temperature

    def fuse(
        self,
        *,
        window: SessionWindow,
        motion: MotionGateResult,
        physio: PhysioNews2Result,
        temperature: TemperatureNews2Result,
    ) -> FusionResult:
        reasons: list[str] = []
        if not window.protocol_ok:
            reasons.extend(window.protocol_reasons)
            return self._abstain(
                STATUS_INCOMPLETE,
                motion,
                physio,
                temperature,
                reasons,
            )
        if motion.level is not SqiLevel.PASS:
            reasons.append(motion.reason)
            return self._abstain(
                STATUS_INVALID,
                motion,
                physio,
                temperature,
                reasons,
            )
        if not physio.complete:
            reasons.append("missing_hr_or_spo2_median")
            return self._abstain(
                STATUS_INVALID,
                motion,
                physio,
                temperature,
                reasons,
            )
        if self.require_temperature and temperature.missing:
            reasons.append("temperature_required_but_missing")
            return self._abstain(
                STATUS_INVALID,
                motion,
                physio,
                temperature,
                reasons,
            )

        components = [physio.hr_score, physio.spo2_score]
        assert physio.hr_score is not None and physio.spo2_score is not None
        n = 2
        temp_score = temperature.news2_score
        if not temperature.missing and temp_score is not None:
            components.append(temp_score)
            n = 3
        elif temperature.missing:
            reasons.append("temperature_omitted_partial_subset")

        total = int(sum(components))
        warning = (
            "subset_sum_only_not_full_NEWS2_do_not_apply_escalation_bands"
        )
        return FusionResult(
            status=STATUS_SCORED,
            algorithm_version=ALGORITHM_VERSION,
            subset_total=total,
            max_subset=NEWS2_MAX_PER_VITAL * n,
            n_components=n,
            hr_score=physio.hr_score,
            spo2_score=physio.spo2_score,
            temp_score=temp_score if not temperature.missing else None,
            sqi_level=motion.level.value,
            motion_passed=True,
            reasons=tuple(reasons),
            warning=warning,
        )

    def _abstain(
        self,
        status: str,
        motion: MotionGateResult,
        physio: PhysioNews2Result,
        temperature: TemperatureNews2Result,
        reasons: list[str],
    ) -> FusionResult:
        return FusionResult(
            status=status,
            algorithm_version=ALGORITHM_VERSION,
            subset_total=None,
            max_subset=None,
            n_components=0,
            hr_score=physio.hr_score,
            spo2_score=physio.spo2_score,
            temp_score=temperature.news2_score,
            sqi_level=motion.level.value,
            motion_passed=motion.passed,
            reasons=tuple(reasons),
            warning="no_clinical_index_fail_closed",
        )
