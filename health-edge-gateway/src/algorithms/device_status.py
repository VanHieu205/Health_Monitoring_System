"""Technical status channel — never mixed into clinical L (PDF §1.2, §7.4)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DeviceStatus(str, Enum):
    DEVICE_OK = "device_ok"
    SIGNAL_POOR = "signal_poor"
    DISCONNECTED = "disconnected"
    BATTERY_LOW = "battery_low"
    NOT_WORN = "not_worn"


@dataclass(frozen=True)
class DeviceStatusResult:
    status: DeviceStatus
    reasons: tuple[str, ...]


def classify_device(
    *,
    heartbeat_age_s: float | None,
    disconnect_s: float = 90.0,
    battery_percent: float | None = None,
    battery_low_pct: float = 15.0,
    worn: bool | None = True,
    ppg_gate_ok: bool | None = None,
    consecutive_ppg_fail: int = 0,
    ppg_fail_to_report: int = 2,
) -> DeviceStatusResult:
    if heartbeat_age_s is None or heartbeat_age_s > disconnect_s:
        return DeviceStatusResult(DeviceStatus.DISCONNECTED, ("heartbeat_timeout",))
    if worn is False:
        return DeviceStatusResult(DeviceStatus.NOT_WORN, ("not_worn",))
    if battery_percent is not None and battery_percent < battery_low_pct:
        return DeviceStatusResult(DeviceStatus.BATTERY_LOW, (f"battery:{battery_percent:g}",))
    if ppg_gate_ok is False and consecutive_ppg_fail >= ppg_fail_to_report:
        return DeviceStatusResult(DeviceStatus.SIGNAL_POOR, ("ppg_gate_fail",))
    return DeviceStatusResult(DeviceStatus.DEVICE_OK, ("device_ok",))
