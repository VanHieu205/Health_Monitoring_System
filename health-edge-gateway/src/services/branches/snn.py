"""arch.snn. The watch publishes the class. This service does not run the net."""

from __future__ import annotations

from typing import Any, Mapping

from services.branches.contract import BranchReading, first_float

ARCHITECTURE = "arch.snn"


def read(payload: Mapping[str, Any]) -> BranchReading:
    raw = payload.get("snn_class")
    if raw is None:
        raw = payload.get("class")
    if raw is None or raw == "":
        return BranchReading(ARCHITECTURE, False)
    return BranchReading(
        ARCHITECTURE,
        True,
        str(raw),
        first_float(payload, "p_fall"),
    )
