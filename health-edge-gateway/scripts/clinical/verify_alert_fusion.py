"""Lab session-pipeline checks aligned with hospital NEWS2 fusion."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))

from domain.fusion import AlertLevel, escalate_with_ml
from domain.sliding_win import SessionWindow
from application.session_pipeline import PipelineConfig, SessionPipeline


def _window(*, hr: float, spo2: float, az: float, flag: int, n: int = 45) -> SessionWindow:
    ts = list(range(1_700_000_000, 1_700_000_000 + n))
    return SessionWindow(
        timestamps=ts,
        hr=[hr] * n,
        spo2=[spo2] * n,
        acc_x=[0.0] * n,
        acc_y=[0.0] * n,
        acc_z=[az] * n,
        event_flags=[flag] * n,
        hr_valid=[hr] * n,
        spo2_valid=[spo2] * n,
        median_hr=hr,
        median_spo2=spo2,
        iqr_hr=0.0,
        iqr_spo2=0.0,
        duration_s=float(n - 1),
        acquire_seconds=45,
        protocol_ok=True,
        has_event_flag_column=True,
    )


def _fall_window() -> SessionWindow:
    n = 40
    ax = [0.0] * 10 + [8000.0] * 3 + [100.0] * 27
    az = [2048.0] * 10 + [500.0] * 3 + [100.0] * 27
    return SessionWindow(
        timestamps=list(range(1_700_000_000, 1_700_000_000 + n)),
        hr=[80.0] * n,
        spo2=[98.0] * n,
        acc_x=ax,
        acc_y=[0.0] * n,
        acc_z=az,
        event_flags=[1] * n,
        hr_valid=[80.0] * n,
        spo2_valid=[98.0] * n,
        median_hr=80.0,
        median_spo2=98.0,
        iqr_hr=0.0,
        iqr_spo2=0.0,
        duration_s=float(n - 1),
        acquire_seconds=45,
        protocol_ok=True,
        has_event_flag_column=True,
    )


def main() -> None:
    pipe = SessionPipeline(PipelineConfig(smv_impact_g=2.0, lsb_per_g=2048.0))
    still = pipe.evaluate(_window(hr=80, spo2=98, az=2048, flag=0))
    assert still.fused.l == 1, still.fused  # S=0 but C<1 → watch, not routine
    assert still.fused.device_status == "device_ok"
    assert still.news2.l_news == 1

    complete = SessionPipeline(
        PipelineConfig(
            smv_impact_g=2.0, lsb_per_g=2048.0,
            rr=16, temperature_c=37.0, sbp=120, consciousness="A", on_oxygen=False,
        )
    ).evaluate(_window(hr=80, spo2=98, az=2048, flag=0))
    assert complete.fused.l == 0, complete.fused

    spo2_low = pipe.evaluate(_window(hr=80, spo2=89, az=2048, flag=0))
    assert spo2_low.fused.l == 2, spo2_low.fused
    assert spo2_low.news2.s_max == 3

    noisy_hr = SessionWindow(
        timestamps=list(range(45)),
        hr=list(range(60, 105)),
        spo2=[98.0] * 45,
        acc_x=[0.0] * 45,
        acc_y=[0.0] * 45,
        acc_z=[2048.0] * 45,
        event_flags=[0] * 45,
        hr_valid=list(range(60, 105)),
        spo2_valid=[98.0] * 45,
        median_hr=80.0,
        median_spo2=98.0,
        iqr_hr=22.0,
        iqr_spo2=0.5,
        duration_s=44.0,
        acquire_seconds=45,
        protocol_ok=True,
    )
    bad_ppg = pipe.evaluate(noisy_hr)
    assert bad_ppg.fused.device_status == "signal_poor", bad_ppg.fused
    assert bad_ppg.fused.l == 1  # missing PPG → incomplete, not a clinical emergency
    assert not bad_ppg.fused.ppg_valid

    fallen = pipe.evaluate(_fall_window())
    assert fallen.fused.l == 3, fallen.fused
    assert fallen.fall_confirm.l_fall == 3

    noisy_and_fall = SessionWindow(
        timestamps=fallen.window.timestamps,
        hr=list(range(60, 100)),
        spo2=fallen.window.spo2,
        acc_x=fallen.window.acc_x,
        acc_y=fallen.window.acc_y,
        acc_z=fallen.window.acc_z,
        event_flags=fallen.window.event_flags,
        hr_valid=list(range(60, 100)),
        spo2_valid=fallen.window.spo2_valid,
        median_hr=80.0,
        median_spo2=98.0,
        iqr_hr=22.0,
        iqr_spo2=0.5,
        duration_s=fallen.window.duration_s,
        protocol_ok=False,
        protocol_reasons=("insufficient_valid_hr:0<30",),
        has_event_flag_column=True,
    )
    both = pipe.evaluate(noisy_and_fall)
    assert both.fused.l == 3, both.fused
    assert both.fused.device_status == "signal_poor"

    alert, src = escalate_with_ml(AlertLevel.ROUTINE, AlertLevel.URGENT)
    assert alert is AlertLevel.URGENT and src == "ml_escalated"
    print("ALL OK")


if __name__ == "__main__":
    main()
