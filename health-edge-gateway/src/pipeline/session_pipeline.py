"""In-process hot path for lab and for services that still read a window.

Watch-side fall rules may run here as a simulator. On a real Pi the fall
service consumes FALL_CANDIDATE and only runs FallConfirmEngine.
"""

from __future__ import annotations

from dataclasses import dataclass

from algorithms.device_status import DeviceStatusResult, classify_device
from algorithms.fall_confirm import FallConfirmEngine, FallConfirmResult
from algorithms.fall_pipeline import FallPipeline, FallPipelineResult
from algorithms.fusion import DecisionFusion, FusionResult
from algorithms.imu_fall_gate import ImuFallGateResult, ImuFallQualityGate
from algorithms.motion_gate import MPU6050_LSB_PER_G, MotionGateResult, MotionQualityGate
from algorithms.news2_branch import (
    News2Branch,
    News2BranchResult,
    News2Inputs,
    VitalObservation,
    VitalSource,
)
from algorithms.physio_rule import PhysioNews2Engine, PhysioNews2Result
from algorithms.ppg_sqi import PpgSqiEngine, PpgSqiResult
from algorithms.sliding_win import SessionWindow
from algorithms.temp_rule import TemperatureNews2Result, TemperatureRuleEngine
from algorithms.trend_branch import TrendBranch, TrendBranchResult
from algorithms.vitals_branch import VitalsBranch, VitalsBranchResult


@dataclass(frozen=True)
class PipelineConfig:
    rms_pass_g: float = 0.05
    rms_fail_g: float = 0.12
    lsb_per_g: float = MPU6050_LSB_PER_G
    max_iqr_hr_bpm: float = 10.0
    max_iqr_spo2_pct: float = 2.0
    core_offset_c: float = 0.0
    min_temp_samples: int = 10
    max_iqr_temp_c: float = 0.3
    require_temperature: bool = False
    review_sum: int = 5
    smv_impact_g: float = 2.5
    fall_cancelled: bool = False
    ppg_sqi_model_pass: bool | None = None
    p_det: float | None = None
    tau_det: float = 0.5
    previous_l: int | None = None
    consecutive_lower: int = 0
    nurse_ack: bool = False
    scale2: bool = False
    rr: float | None = None
    temperature_c: float | None = None
    sbp: float | None = None
    consciousness: str | None = None
    on_oxygen: bool | None = None
    measured_ttl_s: float = 15 * 60
    now: float | None = None


@dataclass(frozen=True)
class PipelineSnapshot:
    window: SessionWindow
    motion: MotionGateResult
    imu_gate: ImuFallGateResult
    fall: FallPipelineResult
    fall_confirm: FallConfirmResult
    physio: PhysioNews2Result
    temperature: TemperatureNews2Result
    ppg_sqi: PpgSqiResult
    vitals: VitalsBranchResult
    news2: News2BranchResult
    trend: TrendBranchResult
    device: DeviceStatusResult
    fused: FusionResult


def _obs(value, *, source: VitalSource, gate_ok: bool, now: float | None, ttl: float) -> VitalObservation:
    if value is None or not gate_ok:
        return VitalObservation()
    until = None if now is None else now + ttl
    return VitalObservation(source=source, value=value, gate_ok=True, measured_at=now, valid_until=until)


class SessionPipeline:
    def __init__(self, config: PipelineConfig | None = None) -> None:
        cfg = config or PipelineConfig()
        self.config = cfg
        self.motion_gate = MotionQualityGate(
            rms_pass_g=cfg.rms_pass_g,
            rms_fail_g=cfg.rms_fail_g,
            lsb_per_g=cfg.lsb_per_g,
        )
        self.imu_fall_gate = ImuFallQualityGate()
        self.fall_pipeline = FallPipeline(
            lsb_per_g=cfg.lsb_per_g,
            smv_impact_g=cfg.smv_impact_g,
        )
        self.fall_confirm = FallConfirmEngine()
        self.physio = PhysioNews2Engine(
            max_iqr_hr_bpm=cfg.max_iqr_hr_bpm,
            max_iqr_spo2_pct=cfg.max_iqr_spo2_pct,
        )
        self.temp_engine = TemperatureRuleEngine(
            core_offset_c=cfg.core_offset_c,
            min_samples=cfg.min_temp_samples,
            max_iqr_c=cfg.max_iqr_temp_c,
        )
        self.ppg_sqi = PpgSqiEngine()
        self.vitals_branch = VitalsBranch(
            require_temperature=cfg.require_temperature,
            review_sum=cfg.review_sum,
        )
        self.news2_branch = News2Branch()
        self.trend_branch = TrendBranch(tau_det=cfg.tau_det)
        self.fusion = DecisionFusion()

    def evaluate(self, window: SessionWindow, *, ml_alert=None) -> PipelineSnapshot:
        del ml_alert
        cfg = self.config
        now = cfg.now
        motion = self.motion_gate.evaluate(window)
        imu_gate = self.imu_fall_gate.evaluate(window)
        fall = self.fall_pipeline.evaluate(
            window, imu_gate, cancelled=cfg.fall_cancelled
        )
        if cfg.fall_cancelled:
            confirm = self.fall_confirm.evaluate(
                elapsed_s=0.0, button_cancel=True, has_candidate=True
            )
        elif window.watch_fall_candidate:
            confirm = self.fall_confirm.evaluate(
                elapsed_s=30.0,
                consecutive_rest_s=20.0,
                has_candidate=True,
            )
        else:
            confirm = self.fall_confirm.evaluate(elapsed_s=0.0, has_candidate=False)

        physio = self.physio.evaluate(window)
        temperature = self.temp_engine.evaluate(window)
        sqi = self.ppg_sqi.evaluate(
            motion=motion,
            physio=physio,
            protocol_ok=window.protocol_ok,
            model_pass=cfg.ppg_sqi_model_pass,
        )
        vitals = self.vitals_branch.evaluate(
            sqi=sqi, physio=physio, temperature=temperature
        )
        ttl = cfg.measured_ttl_s
        news2 = self.news2_branch.evaluate(
            News2Inputs(
                pulse=_obs(physio.hr_bpm, source=VitalSource.MEASURED, gate_ok=sqi.passed, now=now, ttl=ttl),
                spo2=_obs(physio.spo2_percent, source=VitalSource.MEASURED, gate_ok=sqi.passed, now=now, ttl=ttl),
                rr=_obs(cfg.rr, source=VitalSource.ESTIMATED, gate_ok=cfg.rr is not None, now=now, ttl=ttl),
                temperature=_obs(
                    cfg.temperature_c if cfg.temperature_c is not None else temperature.t_core_est_c,
                    source=VitalSource.MANUAL if cfg.temperature_c is not None else VitalSource.ESTIMATED,
                    gate_ok=cfg.temperature_c is not None or temperature.valid,
                    now=now,
                    ttl=ttl,
                ),
                sbp=_obs(cfg.sbp, source=VitalSource.MANUAL, gate_ok=cfg.sbp is not None, now=now, ttl=ttl),
                consciousness=_obs(
                    cfg.consciousness,
                    source=VitalSource.MANUAL,
                    gate_ok=cfg.consciousness is not None,
                    now=now,
                    ttl=ttl,
                ),
                on_oxygen=_obs(
                    cfg.on_oxygen,
                    source=VitalSource.MANUAL,
                    gate_ok=cfg.on_oxygen is not None,
                    now=now,
                    ttl=ttl,
                ),
                scale2=cfg.scale2,
                now=now,
            )
        )
        trend = self.trend_branch.evaluate(p_det=cfg.p_det, l_news=news2.l_news)
        device = classify_device(
            heartbeat_age_s=0.0,
            worn=True,
            ppg_gate_ok=sqi.passed,
            consecutive_ppg_fail=0 if sqi.passed else 2,
        )
        param_by_name = {p.name: p for p in news2.params}
        fused = self.fusion.fuse(
            l_news=news2.l_news,
            l_fall=confirm.l_fall,
            l_trend=trend.l_trend,
            s=news2.s,
            s_max=news2.s_max,
            completeness=news2.completeness,
            n_valid=news2.n_valid,
            missing=news2.missing,
            needs_confirmation=news2.needs_confirmation,
            device_status=device.status,
            previous_l=cfg.previous_l,
            consecutive_lower=cfg.consecutive_lower,
            nurse_ack=cfg.nurse_ack,
            news_reasons=news2.reasons,
            fall_reasons=confirm.reasons,
            trend_reasons=trend.reasons,
            fall_decision=confirm.decision.value,
            hr_score=param_by_name["pulse"].score,
            spo2_score=param_by_name["spo2"].score,
            temp_score=param_by_name["temperature"].score,
            ppg_valid=sqi.passed,
            temp_status=temperature.status,
            sqi_level=motion.reason,
            motion_passed=motion.passed,
        )
        return PipelineSnapshot(
            window=window,
            motion=motion,
            imu_gate=imu_gate,
            fall=fall,
            fall_confirm=confirm,
            physio=physio,
            temperature=temperature,
            ppg_sqi=sqi,
            vitals=vitals,
            news2=news2,
            trend=trend,
            device=device,
            fused=fused,
        )
