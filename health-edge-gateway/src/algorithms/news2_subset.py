"""Compatibility shim: full NEWS2 lives in ``news2.py``.

Older imports (``pulse_score``, ``spo2_scale1_score``, ``ALGORITHM_VERSION``)
keep working. This file is no longer a 3-vital subset scorer.
"""

from algorithms.news2 import (
    ALGORITHM_VERSION,
    AIR_OXYGEN_MAX,
    FL_ARCHITECTURE_FALL,
    FL_ARCHITECTURE_SNN,
    FL_ARCHITECTURE_SQI,
    FL_ARCHITECTURE_TREND,
    NEWS2_MAX_PER_VITAL,
    NEWS2_N_PARAMS,
    pulse_score,
    round_news2_temperature_c,
    spo2_scale1_score,
    temperature_score,
)

__all__ = [
    "ALGORITHM_VERSION",
    "AIR_OXYGEN_MAX",
    "FL_ARCHITECTURE_FALL",
    "FL_ARCHITECTURE_SNN",
    "FL_ARCHITECTURE_SQI",
    "FL_ARCHITECTURE_TREND",
    "NEWS2_MAX_PER_VITAL",
    "NEWS2_N_PARAMS",
    "pulse_score",
    "round_news2_temperature_c",
    "spo2_scale1_score",
    "temperature_score",
]
