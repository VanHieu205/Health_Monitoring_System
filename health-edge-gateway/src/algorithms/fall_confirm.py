"""Pi confirmation of an on-watch FALL_CANDIDATE (PDF §7.2).

The watch already ran impact + SNN fall_like + posture. This module only
opens a 30 s window and decides confirm vs cancel from MOTION / BUTTON.

Missing packets always confirm; they never cancel.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

ACTIVE_CLASSES = frozenset({"walk", "sit_stand"})
RESTISH_CLASSES = frozenset({"rest", "unknown"})


class FallConfirmDecision(str, Enum):
    PENDING = "pending"
    FALL_CONFIRMED = "fall_confirmed"
    AUTO_CANCELLED = "auto_cancelled"
    MANUAL_CANCELLED = "manual_cancelled"
    NONE = "none"


@dataclass(frozen=True)
class FallConfirmResult:
    decision: FallConfirmDecision
    l_fall: int
    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.decision is not FallConfirmDecision.PENDING


def l_fall_of(decision: FallConfirmDecision) -> int:
    if decision is FallConfirmDecision.FALL_CONFIRMED:
        return 3
    if decision in {
        FallConfirmDecision.AUTO_CANCELLED,
        FallConfirmDecision.MANUAL_CANCELLED,
    }:
        return 1
    return 0


class FallConfirmEngine:
    def __init__(
        self,
        *,
        window_s: float = 30.0,
        active_cancel_s: float = 5.0,
        rest_confirm_s: float = 20.0,
    ) -> None:
        self.window_s = window_s
        self.active_cancel_s = active_cancel_s
        self.rest_confirm_s = rest_confirm_s

    def evaluate(
        self,
        *,
        elapsed_s: float,
        consecutive_active_s: float = 0.0,
        consecutive_rest_s: float = 0.0,
        button_cancel: bool = False,
        new_impact: bool = False,
        packets_missing: bool = False,
        has_candidate: bool = True,
    ) -> FallConfirmResult:
        if not has_candidate:
            return FallConfirmResult(FallConfirmDecision.NONE, 0, ("no_event",))

        if packets_missing:
            return FallConfirmResult(
                FallConfirmDecision.FALL_CONFIRMED,
                3,
                ("missing_motion_confirms",),
            )
        if button_cancel:
            return FallConfirmResult(
                FallConfirmDecision.MANUAL_CANCELLED,
                1,
                ("manual_cancelled",),
            )
        if consecutive_active_s >= self.active_cancel_s and not new_impact:
            return FallConfirmResult(
                FallConfirmDecision.AUTO_CANCELLED,
                1,
                (f"auto_cancelled_active:{consecutive_active_s:.1f}s",),
            )
        if consecutive_rest_s >= self.rest_confirm_s:
            return FallConfirmResult(
                FallConfirmDecision.FALL_CONFIRMED,
                3,
                (f"post_impact_rest:{consecutive_rest_s:.1f}s",),
            )
        if elapsed_s >= self.window_s:
            return FallConfirmResult(
                FallConfirmDecision.FALL_CONFIRMED,
                3,
                (f"window_elapsed:{elapsed_s:.1f}s",),
            )
        return FallConfirmResult(
            FallConfirmDecision.PENDING,
            0,
            (f"pending:{elapsed_s:.1f}s",),
        )
