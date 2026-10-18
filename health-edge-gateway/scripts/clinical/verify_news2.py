"""NEWS2 boundary + fusion-rule checks (no MQTT). Target: 100% on this suite."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))

from domain.device_status import DeviceStatus, classify_device
from domain.fall_confirm import FallConfirmEngine
from domain.fusion import DecisionFusion, apply_hysteresis
from domain.news2 import (
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
from domain.news2_branch import News2Branch, News2Inputs, VitalObservation, VitalSource
from domain.trend_branch import TrendBranch


def V(value, source=VitalSource.MEASURED) -> VitalObservation:
    return VitalObservation(source=source, value=value, gate_ok=True)


def test_tables() -> None:
    assert [pulse_score(x) for x in (40, 41, 51, 91, 111, 131)] == [3, 1, 0, 1, 2, 3]
    assert [respiratory_rate_score(x) for x in (8, 9, 12, 21, 25)] == [3, 1, 0, 2, 3]
    assert [spo2_scale1_score(x) for x in (91, 92, 94, 96)] == [3, 2, 1, 0]
    assert [systolic_bp_score(x) for x in (90, 91, 101, 111, 220)] == [3, 2, 1, 0, 3]
    assert temperature_score(35.0) == 3
    assert temperature_score(35.05) == 1  # rounds to 35.1
    assert temperature_score(36.05) == 0  # rounds to 36.1
    assert temperature_score(38.05) == 1
    assert temperature_score(39.1) == 2
    assert consciousness_score("A") == 0
    assert consciousness_score("V") == 3
    assert air_oxygen_score(True) == 2
    assert spo2_scale2_score(90, on_oxygen=False) == 0
    assert spo2_scale2_score(93, on_oxygen=False) == 2
    assert spo2_scale2_score(97, on_oxygen=True) == 3
    assert spo2_scale2_score(94, on_oxygen=True) == 1


def test_risk_map() -> None:
    assert news2_risk_level(0, 0, 1.0) == 0
    assert news2_risk_level(0, 0, 0.4) == 1
    assert news2_risk_level(3, 1, 1.0) == 1
    assert news2_risk_level(3, 3, 1.0) == 2
    assert news2_risk_level(5, 2, 1.0) == 2
    assert news2_risk_level(7, 3, 1.0) == 3


def test_branch_complete_normal() -> None:
    r = News2Branch().evaluate(
        News2Inputs(
            pulse=V(80), spo2=V(98), rr=V(16), temperature=V(37.0),
            sbp=V(120), consciousness=V("A"), on_oxygen=V(False),
        )
    )
    assert r.s == 0 and r.completeness == 1.0 and r.l_news == 0


def test_missing_is_not_low_risk() -> None:
    r = News2Branch().evaluate(News2Inputs(pulse=V(80), spo2=V(98)))
    assert r.s == 0 and r.completeness < 1.0 and r.l_news == 1
    assert "pulse" not in r.missing and "sbp" in r.missing


def test_spo2_red() -> None:
    r = News2Branch().evaluate(News2Inputs(pulse=V(80), spo2=V(89)))
    assert r.s_max == 3 and r.l_news == 2


def test_estimated_needs_confirmation() -> None:
    r = News2Branch().evaluate(
        News2Inputs(
            pulse=V(80), spo2=V(98), rr=V(7, VitalSource.ESTIMATED),
            temperature=V(37.0), sbp=V(120), consciousness=V("A"), on_oxygen=V(False),
        )
    )
    assert r.l_news == 2 and r.needs_confirmation


def test_manual_overrides_auto() -> None:
    r = News2Branch().evaluate(
        News2Inputs(
            pulse=V(80),
            spo2=VitalObservation(VitalSource.MANUAL, 98, True),
            rr=V(16, VitalSource.MANUAL),
            temperature=V(37.0, VitalSource.MANUAL),
            sbp=V(120),
            consciousness=V("A"),
            on_oxygen=V(False),
        )
    )
    assert r.l_news == 0 and r.params[1].source == "manual"


def test_fall_confirm() -> None:
    eng = FallConfirmEngine()
    assert eng.evaluate(elapsed_s=10, packets_missing=True).l_fall == 3
    assert eng.evaluate(elapsed_s=10, button_cancel=True).l_fall == 1
    assert eng.evaluate(elapsed_s=10, consecutive_active_s=5).l_fall == 1
    assert eng.evaluate(elapsed_s=30).l_fall == 3
    assert eng.evaluate(elapsed_s=10, consecutive_rest_s=20).l_fall == 3
    assert not eng.evaluate(elapsed_s=10).ready


def test_trend_cap() -> None:
    t = TrendBranch()
    assert t.evaluate(p_det=0.9, l_news=0).l_trend == 1
    assert t.evaluate(p_det=0.9, l_news=2).l_trend == 2
    assert t.evaluate(p_det=0.9, l_news=3).l_trend == 2
    assert t.evaluate(p_det=0.1, l_news=2).l_trend == 0


def test_fusion_rules() -> None:
    f = DecisionFusion()
    out = f.fuse(l_news=1, l_fall=3, l_trend=2, completeness=0.2, ppg_valid=False)
    assert out.l == 3 and out.alert_source == "fall"
    out = f.fuse(l_news=2, l_fall=0, l_trend=1)
    assert out.l == 2 and out.l >= out.l_news
    out = f.fuse(
        l_news=0, l_fall=0, l_trend=0,
        device_status=DeviceStatus.SIGNAL_POOR,
    )
    assert out.l == 0 and out.device_status == "signal_poor"
    l, held = apply_hysteresis(1, 3, consecutive_lower=0)
    assert l == 3 and held
    l, held = apply_hysteresis(1, 3, consecutive_lower=1)
    assert l == 1 and not held
    l, held = apply_hysteresis(1, 3, consecutive_lower=0, nurse_ack=True)
    assert l == 1 and not held


def test_device_channel() -> None:
    assert classify_device(heartbeat_age_s=120).status is DeviceStatus.DISCONNECTED
    assert classify_device(heartbeat_age_s=1, ppg_gate_ok=False, consecutive_ppg_fail=2).status is DeviceStatus.SIGNAL_POOR
    assert classify_device(heartbeat_age_s=1, ppg_gate_ok=False, consecutive_ppg_fail=1).status is DeviceStatus.DEVICE_OK


def main() -> None:
    test_tables()
    test_risk_map()
    test_branch_complete_normal()
    test_missing_is_not_low_risk()
    test_spo2_red()
    test_estimated_needs_confirmation()
    test_manual_overrides_auto()
    test_fall_confirm()
    test_trend_cap()
    test_fusion_rules()
    test_device_channel()
    print("ALL OK")


if __name__ == "__main__":
    main()
