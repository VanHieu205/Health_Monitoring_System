"""PPG session quality: rest IMU + IQR stability + optional federated SQI model.

The SQI model, when present, may only make a session *stricter* (invalidate).
It never forces a noisy window through to NEWS2 scoring.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.motion_gate import MotionGateResult, SqiLevel
from domain.physio_rule import PhysioNews2Result


@dataclass(frozen=True)
class PpgSqiResult:
    passed: bool
    reasons: tuple[str, ...]
    model_used: bool


class PpgSqiEngine:
    """Combine PPG rest gate, IQR stability, and optional model vote."""

    def evaluate(
        self,
        *,
        motion: MotionGateResult,
        physio: PhysioNews2Result,
        protocol_ok: bool,
        model_pass: bool | None = None,
    ) -> PpgSqiResult:
        reasons: list[str] = []
        if not protocol_ok:
            reasons.append("protocol_not_ok")
        if motion.level is not SqiLevel.PASS:
            reasons.append(motion.reason)
        if not physio.ppg_stable:
            reasons.extend(physio.ppg_reasons)
        if not physio.complete:
            reasons.append("missing_hr_or_spo2_median")
        model_used = model_pass is not None
        if model_pass is False:
            reasons.append("ppg_sqi_model_fail")
        return PpgSqiResult(
            passed=not reasons,
            reasons=tuple(reasons),
            model_used=model_used,
        )
