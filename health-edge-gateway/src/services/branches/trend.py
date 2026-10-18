"""arch.trend. L_trend is computed by TrendBranch from a published p_det.

The level stays at most 2. A missing score leaves the branch at zero.
"""

from __future__ import annotations

from typing import Any, Mapping

from services.branches.contract import BranchReading, first_float

ARCHITECTURE = "arch.trend"


def read(payload: Mapping[str, Any]) -> BranchReading:
    score = first_float(payload, "p_det")
    if score is None:
        return BranchReading(ARCHITECTURE, False)
    return BranchReading(ARCHITECTURE, True, score=score)
