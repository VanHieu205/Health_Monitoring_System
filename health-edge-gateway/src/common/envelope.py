"""Versioned JSON envelope shared by watch → Pi messages."""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "1.0.0"
REQUIRED = ("schema_version", "device_id", "seq", "ts_ms")


class EnvelopeError(ValueError):
    pass


def validate_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in REQUIRED if key not in payload]
    if missing:
        raise EnvelopeError(f"missing fields: {missing}")
    if str(payload["schema_version"]) != SCHEMA_VERSION:
        raise EnvelopeError(f"unsupported schema_version {payload['schema_version']!r}")
    if not str(payload["device_id"]).strip():
        raise EnvelopeError("empty device_id")
    seq = int(payload["seq"])
    if seq < 0:
        raise EnvelopeError("seq must be >= 0")
    return payload
