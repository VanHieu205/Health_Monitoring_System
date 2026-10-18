"""arch.sqi. A published pass/fail may only reject a PPG session.

Absent fields leave the IQR gate unchanged. The model never forces a
noisy session through to NEWS2.
"""

from __future__ import annotations

from typing import Any, Mapping

from services.branches.contract import BranchReading, first_float

ARCHITECTURE = "arch.sqi"


def read(payload: Mapping[str, Any]) -> BranchReading:
    if "sqi_pass" in payload and payload.get("sqi_pass") is not None:
        passed = bool(payload.get("sqi_pass"))
        return BranchReading(ARCHITECTURE, True, "pass" if passed else "fail")
    score = first_float(payload, "p_good")
    if score is None:
        return BranchReading(ARCHITECTURE, False)
    return BranchReading(ARCHITECTURE, True, score=score)
