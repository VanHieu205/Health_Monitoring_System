"""Watch-feature → vital values on the Pi (PDF §5). Not NEWS2 scoring."""

from __future__ import annotations

from statistics import median
from typing import Sequence

IBI_MIN_S = 0.27
IBI_MAX_S = 2.0
IBI_MAX_REL = 0.20
RR_AGREE_BPM = 4.0


def filter_ibi(ibi_s: Sequence[float]) -> list[float]:
    raw = [float(x) for x in ibi_s if IBI_MIN_S <= float(x) <= IBI_MAX_S]
    if len(raw) < 3:
        return raw
    mid = median(raw)
    return [x for x in raw if abs(x - mid) <= IBI_MAX_REL * mid]


def hr_from_ibi(ibi_s: Sequence[float]) -> float | None:
    kept = filter_ibi(ibi_s)
    if not kept:
        return None
    return 60.0 / float(median(kept))


def spo2_from_r(r_values: Sequence[float], *, a: float, b: float, c: float) -> float | None:
    if not r_values:
        return None
    samples = []
    for r in r_values:
        spo2 = a * float(r) ** 2 + b * float(r) + c
        samples.append(min(100.0, max(70.0, spo2)))
    return float(median(samples))


def rr_from_modulations(f_riiv: float, f_riav: float, f_rifv: float) -> float | None:
    """Frequencies in Hz. Accept only when the three estimates agree within 4 /min."""
    bpm = [60.0 * float(f_riiv), 60.0 * float(f_riav), 60.0 * float(f_rifv)]
    if max(bpm) - min(bpm) > RR_AGREE_BPM:
        return None
    return float(median(bpm))
