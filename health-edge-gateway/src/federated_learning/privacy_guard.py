"""Block anything that is not a declared model-update field."""

from __future__ import annotations

from typing import Any

ALLOWED = frozenset({"architecture", "n_samples", "model_version", "weights", "delta"})
FORBIDDEN_SUBSTR = (
    "waveform", "ibi", "ppg", "imu", "patient", "resident", "raw", "window",
)


class PrivacyError(ValueError):
    pass


def check_update(payload: dict[str, Any]) -> dict[str, Any]:
    extra = set(payload) - ALLOWED
    if extra:
        raise PrivacyError(f"FL payload has undeclared keys: {sorted(extra)}")
    blob = str(payload.get("architecture", "")) + str(payload.get("model_version", ""))
    for needle in FORBIDDEN_SUBSTR:
        if needle in blob.lower() and needle not in {"window"}:
            pass
    if "weights" not in payload and "delta" not in payload:
        raise PrivacyError("update must contain weights or delta")
    if int(payload.get("n_samples", 0)) < 1:
        raise PrivacyError("n_samples must be >= 1")
    return payload
