"""NEWS2 cut-points for vitals the watch can measure in a seated PPG session.

Source (must be cited in the thesis / IFU):

    Royal College of Physicians (2017). *National Early Warning Score
    (NEWS) 2*. London: RCP.

This module is **not** a full NEWS2 implementation. Full NEWS2 also
requires respiratory rate, systolic blood pressure, consciousness
(ACVPU) and supplemental oxygen. Applying the published *escalation
bands* (low / medium / high) to a 3-vital subset would be clinically
misleading, so callers must treat the integer scores as a **documented
subset sum only**.

SpO2 uses **Scale 1** (patients without hypercapnic respiratory
failure). Scale 2 is not selected automatically.
"""

from __future__ import annotations

ALGORITHM_VERSION = "3.0.0-care-home-alert-fusion"
FL_ARCHITECTURE_FALL = "arch.fall"
FL_ARCHITECTURE_SQI = "arch.sqi"

# Maximum NEWS2 points for one vital.
NEWS2_MAX_PER_VITAL = 3


def round_news2_temperature_c(temperature_c: float) -> float:
    """NEWS2 charts are tabulated to 0.1 °C."""
    return round(float(temperature_c), 1)


def pulse_score(heart_rate_bpm: float) -> int:
    """NEWS2 pulse (beats per minute)."""
    hr = float(heart_rate_bpm)
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


def spo2_scale1_score(spo2_percent: float) -> int:
    """NEWS2 oxygen saturation Scale 1 (percent).

    Lookup uses the integer percent (clinical pulse-ox display).
    """
    s = int(round(float(spo2_percent)))
    if s <= 91:
        return 3
    if s <= 93:
        return 2
    if s <= 95:
        return 1
    return 0


def temperature_score(temperature_c: float) -> int:
    """NEWS2 temperature after rounding to 0.1 °C."""
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
