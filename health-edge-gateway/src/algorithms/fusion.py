"""Decision-level fusion: combine branch *decisions* into a nurse alert.

This module does not weight probabilities. Fall, vitals, and device
branches are gated independently; fusion applies a priority table.

    fall_alert    always wins
    vitals_invalid never becomes vital_alert
    PPG fail does not block fall_alert
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from algorithms.fall_pipeline import FallDecision, FallPipelineResult
from algorithms.imu_fall_gate import ImuFallGateResult
from algorithms.news2_subset import ALGORITHM_VERSION
from algorithms.vitals_branch import VitalsBranchResult, VitalsDecision


class AlertLevel(str, Enum):
    OK = "ok"
    SIGNAL_POOR = "signal_poor"
    CHECK_IN = "check_in"
    VITAL_ALERT = "vital_alert"
    FALL_ALERT = "fall_alert"

    @property
    def rank(self) -> int:
        return _ALERT_RANK[self]


_ALERT_RANK = {
    AlertLevel.OK: 0,
    AlertLevel.SIGNAL_POOR: 1,
    AlertLevel.CHECK_IN: 2,
    AlertLevel.VITAL_ALERT: 3,
    AlertLevel.FALL_ALERT: 4,
}

# Backward-compatible names used in older kiosk logs.
Tier = AlertLevel


@dataclass(frozen=True)
class FusionResult:
    status: str
    algorithm_version: str
    alert_level: str
    alert_source: str
    tier: str
    tier_source: str
    subset_total: int | None
    max_component: int | None
    completeness: float
    n_components: int
    max_subset: int | None
    hr_score: int | None
    spo2_score: int | None
    temp_score: int | None
    ppg_valid: bool
    fall_decision: str
    temp_status: str
    sqi_level: str
    motion_passed: bool
    reasons: tuple[str, ...]
    warning: str


class DecisionFusion:
    """Priority fusion over fall + vitals decisions."""

    def fuse(
        self,
        *,
        fall: FallPipelineResult,
        vitals: VitalsBranchResult,
        imu_gate: ImuFallGateResult,
        temp_status: str,
        ppg_motion_reason: str,
        motion_passed: bool,
        ml_alert: AlertLevel | None = None,
    ) -> FusionResult:
        reasons = list(fall.reasons) + list(vitals.reasons)
        rule = self._rule_alert(fall, vitals)
        alert, source = escalate_with_ml(rule, ml_alert)
        ppg_valid = vitals.decision is not VitalsDecision.INVALID
        if fall.decision is FallDecision.FALL:
            status = "fall_alert"
        elif ppg_valid:
            status = "scored"
        elif fall.decision is FallDecision.IMU_UNRELIABLE and not ppg_valid:
            status = "invalid_measurement"
        else:
            status = "invalid_measurement"
        warning = vitals.warning
        if fall.decision is FallDecision.FALL:
            warning = "fall_alert_independent_of_ppg"
        return FusionResult(
            status=status,
            algorithm_version=ALGORITHM_VERSION,
            alert_level=alert.value,
            alert_source=source,
            tier=alert.value,
            tier_source=source,
            subset_total=vitals.subset_total,
            max_component=vitals.max_component,
            completeness=vitals.completeness,
            n_components=vitals.n_components,
            max_subset=vitals.max_subset,
            hr_score=vitals.hr_score,
            spo2_score=vitals.spo2_score,
            temp_score=vitals.temp_score,
            ppg_valid=ppg_valid,
            fall_decision=fall.decision.value,
            temp_status=temp_status,
            sqi_level=ppg_motion_reason,
            motion_passed=motion_passed,
            reasons=tuple(reasons),
            warning=warning,
        )

    def _rule_alert(
        self, fall: FallPipelineResult, vitals: VitalsBranchResult
    ) -> AlertLevel:
        if fall.decision is FallDecision.FALL:
            return AlertLevel.FALL_ALERT
        if fall.decision is FallDecision.POSSIBLE_FALL:
            if vitals.decision is VitalsDecision.URGENT:
                return AlertLevel.VITAL_ALERT
            return AlertLevel.CHECK_IN
        if fall.decision is FallDecision.CANCELLED:
            base = AlertLevel.CHECK_IN
        else:
            base = AlertLevel.OK

        if vitals.decision is VitalsDecision.URGENT:
            return AlertLevel.VITAL_ALERT
        if vitals.decision is VitalsDecision.WATCH:
            return AlertLevel.CHECK_IN
        if vitals.decision is VitalsDecision.INVALID:
            if fall.decision is FallDecision.IMU_UNRELIABLE:
                return AlertLevel.SIGNAL_POOR
            return AlertLevel.SIGNAL_POOR
        if base is AlertLevel.CHECK_IN:
            return AlertLevel.CHECK_IN
        return AlertLevel.OK


def escalate_with_ml(
    rule_alert: AlertLevel, ml_alert: AlertLevel | None
) -> tuple[AlertLevel, str]:
    """ML may raise the alert of a scored session, never lower it."""
    if (
        ml_alert is None
        or rule_alert is AlertLevel.SIGNAL_POOR
        or ml_alert is AlertLevel.SIGNAL_POOR
    ):
        return rule_alert, "rule"
    if ml_alert.rank > rule_alert.rank:
        return ml_alert, "ml_escalated"
    return rule_alert, "rule"
