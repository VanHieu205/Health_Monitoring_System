"""Deterioration-forecast branch (PDF §7.3).

May raise L by at most one step and never above 2. Labels come from the
site's own NEWS2 history, not from a disease model.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_TAU_DET = 0.5


@dataclass(frozen=True)
class TrendBranchResult:
    l_trend: int
    p_det: float
    triggered: bool
    reasons: tuple[str, ...]


class TrendBranch:
    def __init__(self, *, tau_det: float = DEFAULT_TAU_DET) -> None:
        if not 0.0 < tau_det < 1.0:
            raise ValueError("tau_det must be in (0, 1)")
        self.tau_det = tau_det

    def evaluate(self, *, p_det: float | None, l_news: int) -> TrendBranchResult:
        if p_det is None:
            return TrendBranchResult(0, 0.0, False, ("trend_unavailable",))
        p = float(p_det)
        if p >= self.tau_det:
            level = min(int(l_news) + 1, 2)
            return TrendBranchResult(
                level, p, True, (f"p_det:{p:.2f}", f"l_trend:{level}"),
            )
        return TrendBranchResult(0, p, False, (f"p_det_below_tau:{p:.2f}",))
