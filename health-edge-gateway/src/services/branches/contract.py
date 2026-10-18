"""Reading a branch publishes. Services do not import checkpoints here."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class BranchReading:
    architecture: str
    available: bool
    label: str | None = None
    score: float | None = None


def first_float(payload: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        raw = payload.get(key)
        if raw is None or raw == "":
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None
    return None
