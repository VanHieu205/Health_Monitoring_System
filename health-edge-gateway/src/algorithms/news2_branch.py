"""NEWS2 branch: combine gated automatic vitals with nurse-entered values.

Missing parameters are omitted from S (a lower bound on the true score).
S = 0 with C < 1 is never reported as low risk (L_news = 1).
Estimated RR/temperature that alone raise the risk band need confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from algorithms.news2 import (
    ALGORITHM_VERSION,
    NEWS2_N_PARAMS,
    air_oxygen_score,
    consciousness_score,
    news2_risk_level,
    pulse_score,
    respiratory_rate_score,
    spo2_scale1_score,
    spo2_scale2_score,
    systolic_bp_score,
    temperature_score,
)


class VitalSource(str, Enum):
    MEASURED = "measured"
    ESTIMATED = "estimated"
    MANUAL = "manual"
    MISSING = "missing"


@dataclass(frozen=True)
class VitalObservation:
    source: VitalSource = VitalSource.MISSING
    value: float | str | bool | None = None
    gate_ok: bool = False
    measured_at: float | None = None
    valid_until: float | None = None

    def usable(self, now: float | None) -> bool:
        if self.source is VitalSource.MISSING or not self.gate_ok or self.value is None:
            return False
        if now is not None and self.valid_until is not None and now > self.valid_until:
            return False
        return True


@dataclass(frozen=True)
class News2Inputs:
    pulse: VitalObservation = VitalObservation()
    spo2: VitalObservation = VitalObservation()
    rr: VitalObservation = VitalObservation()
    temperature: VitalObservation = VitalObservation()
    sbp: VitalObservation = VitalObservation()
    consciousness: VitalObservation = VitalObservation()
    on_oxygen: VitalObservation = VitalObservation()
    scale2: bool = False
    now: float | None = None


@dataclass(frozen=True)
class ScoredParam:
    name: str
    score: int | None
    source: str
    value: float | str | bool | None
    missing: bool
    estimated: bool
    max_if_missing: int


@dataclass(frozen=True)
class News2BranchResult:
    l_news: int
    s: int
    s_max: int
    completeness: float
    n_valid: int
    missing: tuple[str, ...]
    params: tuple[ScoredParam, ...]
    needs_confirmation: bool
    reasons: tuple[str, ...]
    algorithm_version: str = ALGORITHM_VERSION

    @property
    def decision_name(self) -> str:
        return {0: "routine", 1: "watch", 2: "urgent", 3: "emergency"}[self.l_news]


def _pick(auto: VitalObservation, manual: VitalObservation, now: float | None) -> VitalObservation:
    """Manual wins when both are still valid (calibrated clinical device)."""
    man_ok = manual.usable(now)
    auto_ok = auto.usable(now)
    if man_ok:
        return manual
    if auto_ok:
        return auto
    return VitalObservation()


class News2Branch:
    def evaluate(self, inputs: News2Inputs) -> News2BranchResult:
        now = inputs.now
        on_ox_obs = inputs.on_oxygen if inputs.on_oxygen.usable(now) else VitalObservation(
            source=VitalSource.MISSING, value=False, gate_ok=False
        )
        on_oxygen = bool(on_ox_obs.value) if on_ox_obs.usable(now) else False
        on_oxygen_known = on_ox_obs.usable(now)

        scored = (
            _score_rr(inputs.rr, now),
            _score_spo2(inputs.spo2, now, inputs.scale2, on_oxygen, on_oxygen_known),
            _score_air(on_ox_obs, now, on_oxygen_known, on_oxygen),
            _score_sbp(inputs.sbp, now),
            _score_pulse(inputs.pulse, now),
            _score_cns(inputs.consciousness, now),
            _score_temp(inputs.temperature, now),
        )
        valid = [p for p in scored if p.score is not None]
        s = int(sum(p.score or 0 for p in valid))
        s_max = int(max((p.score or 0 for p in valid), default=0))
        c = len(valid) / NEWS2_N_PARAMS
        l_news = news2_risk_level(s, s_max, c)

        without_est = [p for p in scored if p.score is not None and not p.estimated]
        s2 = int(sum(p.score or 0 for p in without_est))
        smax2 = int(max((p.score or 0 for p in without_est), default=0))
        c2 = len(without_est) / NEWS2_N_PARAMS
        l_without_est = news2_risk_level(s2, smax2, c2)
        needs = l_news > l_without_est

        reasons = [f"S={s}", f"Smax={s_max}", f"C={c:.2f}"]
        missing = tuple(p.name for p in scored if p.missing)
        if missing:
            reasons.append("missing:" + ",".join(missing))
        if c < 1.0:
            reasons.append("lower_bound_score")
        if needs:
            reasons.append("needs_confirmation")
        if inputs.scale2:
            reasons.append("spo2_scale2")
        return News2BranchResult(
            l_news=l_news,
            s=s,
            s_max=s_max,
            completeness=round(c, 3),
            n_valid=len(valid),
            missing=missing,
            params=scored,
            needs_confirmation=needs,
            reasons=tuple(reasons),
        )


def _score_pulse(obs: VitalObservation, now: float | None) -> ScoredParam:
    if not obs.usable(now):
        return ScoredParam("pulse", None, obs.source.value, obs.value, True, False, 3)
    return ScoredParam(
        "pulse", pulse_score(float(obs.value)), obs.source.value, obs.value, False,
        obs.source is VitalSource.ESTIMATED, 3,
    )


def _score_spo2(
    obs: VitalObservation, now: float | None, scale2: bool, on_oxygen: bool, on_oxygen_known: bool
) -> ScoredParam:
    if not obs.usable(now):
        return ScoredParam("spo2", None, obs.source.value, obs.value, True, False, 3)
    if scale2 and not on_oxygen_known:
        return ScoredParam("spo2", None, obs.source.value, obs.value, True, False, 3)
    score = (
        spo2_scale2_score(float(obs.value), on_oxygen=on_oxygen)
        if scale2
        else spo2_scale1_score(float(obs.value))
    )
    return ScoredParam(
        "spo2", score, obs.source.value, obs.value, False,
        obs.source is VitalSource.ESTIMATED, 3,
    )


def _score_rr(obs: VitalObservation, now: float | None) -> ScoredParam:
    if not obs.usable(now):
        return ScoredParam("rr", None, obs.source.value, obs.value, True, False, 3)
    return ScoredParam(
        "rr", respiratory_rate_score(float(obs.value)), obs.source.value, obs.value, False,
        obs.source is VitalSource.ESTIMATED, 3,
    )


def _score_temp(obs: VitalObservation, now: float | None) -> ScoredParam:
    if not obs.usable(now):
        return ScoredParam("temperature", None, obs.source.value, obs.value, True, False, 3)
    return ScoredParam(
        "temperature", temperature_score(float(obs.value)), obs.source.value, obs.value,
        False, obs.source is VitalSource.ESTIMATED, 3,
    )


def _score_sbp(obs: VitalObservation, now: float | None) -> ScoredParam:
    if not obs.usable(now):
        return ScoredParam("sbp", None, obs.source.value, obs.value, True, False, 3)
    return ScoredParam(
        "sbp", systolic_bp_score(float(obs.value)), obs.source.value, obs.value, False, False, 3,
    )


def _score_cns(obs: VitalObservation, now: float | None) -> ScoredParam:
    if not obs.usable(now):
        return ScoredParam("consciousness", None, obs.source.value, obs.value, True, False, 3)
    return ScoredParam(
        "consciousness", consciousness_score(str(obs.value)), obs.source.value, obs.value,
        False, False, 3,
    )


def _score_air(
    obs: VitalObservation, now: float | None, known: bool, on_oxygen: bool
) -> ScoredParam:
    if not known or not obs.usable(now):
        return ScoredParam("air_oxygen", None, obs.source.value, obs.value, True, False, 2)
    return ScoredParam(
        "air_oxygen", air_oxygen_score(on_oxygen), obs.source.value, on_oxygen, False, False, 2,
    )
