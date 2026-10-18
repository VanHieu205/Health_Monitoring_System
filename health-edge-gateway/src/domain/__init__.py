"""Pure scientific layer: no MQTT, no SQLite, no HTTP."""

from domain.device_status import DeviceStatus, DeviceStatusResult, classify_device
from domain.fall_confirm import FallConfirmDecision, FallConfirmEngine, FallConfirmResult
from domain.fall_pipeline import FallDecision, FallPipeline, FallPipelineResult
from domain.fusion import AlertLevel, DecisionFusion, FusionResult, apply_hysteresis, escalate_with_ml
from domain.imu_fall_gate import ImuFallGateResult, ImuFallQualityGate
from domain.motion_gate import MotionGateResult, MotionQualityGate, SqiLevel
from domain.news2 import (
    ALGORITHM_VERSION,
    FL_ARCHITECTURE_SNN,
    FL_ARCHITECTURE_SQI,
    FL_ARCHITECTURE_TREND,
)
from domain.news2_branch import News2Branch, News2BranchResult, News2Inputs, VitalObservation, VitalSource
from domain.physio_rule import PhysioNews2Engine, PhysioNews2Result
from domain.ppg_sqi import PpgSqiEngine, PpgSqiResult
from domain.sliding_win import SessionWindow, SlidingWindowExtractor
from domain.temp_rule import TemperatureNews2Result, TemperatureRuleEngine
from domain.trend_branch import TrendBranch, TrendBranchResult
from domain.vitals_branch import VitalsBranch, VitalsBranchResult, VitalsDecision

__all__ = [
    "ALGORITHM_VERSION",
    "AlertLevel",
    "DecisionFusion",
    "DeviceStatus",
    "DeviceStatusResult",
    "FL_ARCHITECTURE_SNN",
    "FL_ARCHITECTURE_SQI",
    "FL_ARCHITECTURE_TREND",
    "FallConfirmDecision",
    "FallConfirmEngine",
    "FallConfirmResult",
    "FallDecision",
    "FallPipeline",
    "FallPipelineResult",
    "FusionResult",
    "ImuFallGateResult",
    "ImuFallQualityGate",
    "MotionGateResult",
    "MotionQualityGate",
    "News2Branch",
    "News2BranchResult",
    "News2Inputs",
    "PhysioNews2Engine",
    "PhysioNews2Result",
    "PpgSqiEngine",
    "PpgSqiResult",
    "SessionWindow",
    "SlidingWindowExtractor",
    "SqiLevel",
    "TemperatureNews2Result",
    "TemperatureRuleEngine",
    "TrendBranch",
    "TrendBranchResult",
    "VitalObservation",
    "VitalSource",
    "VitalsBranch",
    "VitalsBranchResult",
    "VitalsDecision",
    "apply_hysteresis",
    "classify_device",
    "escalate_with_ml",
]
