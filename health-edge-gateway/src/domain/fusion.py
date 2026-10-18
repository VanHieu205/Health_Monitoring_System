"""Decision-level fusion: L = max(L_news, L_fall, L_trend) (PDF §7.4).

Hard rules
----------
1. Escalate-only across branches (max). ML cannot lower NEWS2.
2. NEWS2 is a floor: L >= L_news.
3. Fall is independent of PPG quality.
4. Technical status is a separate channel and never written into L.
5. L rises immediately; it falls only after two consecutive lower sessions
   or a nurse acknowledgement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from domain.device_status import DeviceStatus
from domain.news2 import ALGORITHM_VERSION

LEVEL_NAME = {0: "routine", 1: "watch", 2: "urgent", 3: "emergency"}


class AlertLevel(IntEnum):
    ROUTINE = 0
    WATCH = 1
    URGENT = 2
    EMERGENCY = 3

    @property
    def label(self) -> str:
        return LEVEL_NAME[int(self)]


# Names kept so older lab logs can still import a string enum-like alias.
class _Legacy:
    OK = "routine"
    SIGNAL_POOR = "signal_poor"
    CHECK_IN = "watch"
    VITAL_ALERT = "urgent"
    FALL_ALERT = "emergency"


Tier = AlertLevel


@dataclass(frozen=True)
class FusionResult:
    status: str
    algorithm_version: str
    l: int
    alert_level: str
    alert_source: str
    l_news: int
    l_fall: int
    l_trend: int
    s: int
    s_max: int
    completeness: float
    n_valid: int
    missing: tuple[str, ...]
    needs_confirmation: bool
    device_status: str
    reasons: tuple[str, ...]
    warning: str
    # Compatibility fields used by fusion_worker / older JSON.
    tier: str
    tier_source: str
    subset_total: int | None
    max_component: int | None
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

    @property
    def hysteresis_held(self) -> bool:
        return "hysteresis_hold" in self.reasons


class DecisionFusion:
    def fuse(
        self,
        *,
        l_news: int,
        l_fall: int,
        l_trend: int = 0,
        s: int = 0,
        s_max: int = 0,
        completeness: float = 0.0,
        n_valid: int = 0,
        missing: tuple[str, ...] = (),
        needs_confirmation: bool = False,
        device_status: DeviceStatus | str = DeviceStatus.DEVICE_OK,
        previous_l: int | None = None,
        consecutive_lower: int = 0,
        nurse_ack: bool = False,
        news_reasons: tuple[str, ...] = (),
        fall_reasons: tuple[str, ...] = (),
        trend_reasons: tuple[str, ...] = (),
        fall_decision: str = "none",
        hr_score: int | None = None,
        spo2_score: int | None = None,
        temp_score: int | None = None,
        ppg_valid: bool = True,
        temp_status: str = "unknown",
        sqi_level: str = "",
        motion_passed: bool = True,
    ) -> FusionResult:
        raw = max(int(l_news), int(l_fall), int(l_trend))
        l, held = apply_hysteresis(
            raw, previous_l, consecutive_lower=consecutive_lower, nurse_ack=nurse_ack
        )
        source = _source(l, int(l_news), int(l_fall), int(l_trend))
        reasons = list(news_reasons) + list(fall_reasons) + list(trend_reasons)
        reasons.append(f"L={l}")
        reasons.append(f"source:{source}")
        if held:
            reasons.append("hysteresis_hold")
        if int(l_fall) == 3:
            warning = "fall_independent_of_ppg"
            status = "emergency"
        elif needs_confirmation:
            warning = "needs_confirmation"
            status = LEVEL_NAME[l]
        else:
            warning = "news2_lower_bound_if_incomplete"
            status = LEVEL_NAME[l]
        device = (
            device_status.value if isinstance(device_status, DeviceStatus) else str(device_status)
        )
        return FusionResult(
            status=status,
            algorithm_version=ALGORITHM_VERSION,
            l=l,
            alert_level=LEVEL_NAME[l],
            alert_source=source,
            l_news=int(l_news),
            l_fall=int(l_fall),
            l_trend=int(l_trend),
            s=int(s),
            s_max=int(s_max),
            completeness=float(completeness),
            n_valid=int(n_valid),
            missing=tuple(missing),
            needs_confirmation=needs_confirmation,
            device_status=device,
            reasons=tuple(reasons),
            warning=warning,
            tier=LEVEL_NAME[l],
            tier_source=source,
            subset_total=int(s),
            max_component=int(s_max),
            n_components=int(n_valid),
            max_subset=21,
            hr_score=hr_score,
            spo2_score=spo2_score,
            temp_score=temp_score,
            ppg_valid=ppg_valid,
            fall_decision=fall_decision,
            temp_status=temp_status,
            sqi_level=sqi_level,
            motion_passed=motion_passed,
        )


def apply_hysteresis(
    raw: int,
    previous_l: int | None,
    *,
    consecutive_lower: int = 0,
    nurse_ack: bool = False,
    hold_sessions: int = 2,
) -> tuple[int, bool]:
    if previous_l is None or raw >= previous_l or nurse_ack:
        return raw, False
    if consecutive_lower + 1 >= hold_sessions:
        return raw, False
    return previous_l, True


def escalate_with_ml(rule_alert: AlertLevel | int, ml_alert: AlertLevel | int | None):
    """Kept for tests: ML may only raise, and never writes the technical channel."""
    if ml_alert is None:
        return AlertLevel(int(rule_alert)), "rule"
    raised = max(int(rule_alert), int(ml_alert))
    src = "ml_escalated" if raised > int(rule_alert) else "rule"
    return AlertLevel(raised), src


def _source(l: int, l_news: int, l_fall: int, l_trend: int) -> str:
    if l_fall == l and l_fall >= l_news and l_fall >= l_trend:
        return "fall"
    if l_news == l:
        return "news2"
    if l_trend == l:
        return "trend"
    return "news2"
