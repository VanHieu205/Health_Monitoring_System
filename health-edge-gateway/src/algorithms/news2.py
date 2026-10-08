"""Full NEWS2 tables (Royal College of Physicians, 2017).

Cut-points are clinical standard, not trainable and not federated.
Scale 2 is used only when a clinician enables it; the system never
selects the scale automatically.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

ALGORITHM_VERSION = "4.0.0-hospital-news2"
NEWS2_N_PARAMS = 7
NEWS2_MAX_PER_VITAL = 3
AIR_OXYGEN_MAX = 2

FL_ARCHITECTURE_SNN = "arch.snn"
FL_ARCHITECTURE_SQI = "arch.sqi"
FL_ARCHITECTURE_TREND = "arch.trend"
# Kept so older FL env values still parse as allowed-or-rejected explicitly.
FL_ARCHITECTURE_FALL = "arch.snn"


def _half_up(value: float, quant: str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(quant), rounding=ROUND_HALF_UP)


def round_hr(value: float) -> int:
    return int(_half_up(value, "1"))


def round_rr(value: float) -> int:
    return int(_half_up(value, "1"))


def round_sbp(value: float) -> int:
    return int(_half_up(value, "1"))


def round_spo2(value: float) -> int:
    return int(_half_up(value, "1"))


def round_news2_temperature_c(temperature_c: float) -> float:
    return float(_half_up(temperature_c, "0.1"))


def pulse_score(heart_rate_bpm: float) -> int:
    hr = round_hr(heart_rate_bpm)
    if hr <= 40:
        return 3
    if hr <= 50:
        return 1
    if hr <= 90:
        return 0
    if hr <= 110:
        return 1
    if hr <= 130:
        return 2
    return 3


def respiratory_rate_score(rr_per_min: float) -> int:
    rr = round_rr(rr_per_min)
    if rr <= 8:
        return 3
    if rr <= 11:
        return 1
    if rr <= 20:
        return 0
    if rr <= 24:
        return 2
    return 3


def spo2_scale1_score(spo2_percent: float) -> int:
    s = round_spo2(spo2_percent)
    if s <= 91:
        return 3
    if s <= 93:
        return 2
    if s <= 95:
        return 1
    return 0


def spo2_scale2_score(spo2_percent: float, *, on_oxygen: bool) -> int:
    s = round_spo2(spo2_percent)
    if s <= 83:
        return 3
    if s <= 85:
        return 2
    if s <= 87:
        return 1
    if s <= 92:
        return 0
    if on_oxygen:
        if s >= 97:
            return 3
        if s >= 95:
            return 2
        return 1
    return 2


def air_oxygen_score(on_oxygen: bool) -> int:
    return 2 if on_oxygen else 0


def systolic_bp_score(sbp_mmhg: float) -> int:
    sbp = round_sbp(sbp_mmhg)
    if sbp <= 90:
        return 3
    if sbp <= 100:
        return 2
    if sbp <= 110:
        return 1
    if sbp <= 219:
        return 0
    return 3


def consciousness_score(acvpu: str) -> int:
    letter = str(acvpu).strip().upper()[:1]
    if letter == "A":
        return 0
    if letter in {"C", "V", "P", "U"}:
        return 3
    raise ValueError(f"invalid ACVPU: {acvpu!r}")


def temperature_score(temperature_c: float) -> int:
    t = round_news2_temperature_c(temperature_c)
    if t <= 35.0:
        return 3
    if t <= 36.0:
        return 1
    if t <= 38.0:
        return 0
    if t <= 39.0:
        return 1
    return 2


def news2_risk_level(s: int, s_max: int, completeness: float) -> int:
    """Map NEWS2 total onto L_news in {0,1,2,3} (PDF eq. 15, top-down)."""
    if s >= 7:
        return 3
    if 5 <= s <= 6 or s_max == 3:
        return 2
    if 1 <= s <= 4 or (s == 0 and completeness < 1.0):
        return 1
    return 0


def manual_ttl_hours(s: int, s_max: int) -> int:
    """Validity Θ of nurse-entered values from the latest risk band (PDF eq. 10)."""
    if s == 0:
        return 12
    if 1 <= s <= 4 and s_max < 3:
        return 6
    return 1
