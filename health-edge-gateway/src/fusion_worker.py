"""Lab hot-path: SQLite → SessionPipeline → JSON log.

Independent of ``mqtt_subscriber`` (shared SQLite only). Prefer
``services/fusion_service.py`` when running the microservice set.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from common.config import load_gateway_env, sensor_table, sqlite_path

load_gateway_env()

from algorithms.news2_subset import ALGORITHM_VERSION
from algorithms.sliding_win import SlidingWindowExtractor
from services.env_pipeline import pipeline_from_env

LOGGER = logging.getLogger("fusion_worker")
DEFAULT_INTERVAL_S = 10.0


@dataclass(frozen=True)
class SessionFusionReport:
    ok: bool
    status: str
    algorithm_version: str
    alert_level: str
    alert_source: str
    fall_decision: str
    vitals_decision: str
    n_samples: int
    n_raw_fetched: int
    duration_s: float
    protocol_ok: bool
    median_hr: float | None
    median_spo2: float | None
    median_temp: float | None
    iqr_hr: float | None
    iqr_spo2: float | None
    iqr_temp: float | None
    hr_score: int | None
    spo2_score: int | None
    temp_score: int | None
    subset_total: int | None
    max_component: int | None
    completeness: float
    max_subset: int | None
    n_components: int
    ppg_valid: bool
    temp_status: str
    sqi_level: str | None
    rms_dyn_g: float | None
    motion_passed: bool | None
    smv_peak_g: float | None
    reasons: tuple[str, ...]
    warning: str
    tier: str
    tier_source: str


def run_once() -> SessionFusionReport:
    extractor = SlidingWindowExtractor(
        sqlite_path(),
        table=os.getenv("SENSOR_TABLE", sensor_table()),
        settle_seconds=int(os.getenv("SETTLE_SECONDS", "15")),
        acquire_seconds=int(os.getenv("ACQUIRE_SECONDS", "45")),
    )
    snap = pipeline_from_env().evaluate(extractor.fetch())
    fused = snap.fused
    scored = fused.alert_level in {"ok", "check_in", "vital_alert", "fall_alert"} and fused.ppg_valid
    if fused.alert_level == "fall_alert":
        scored = True
    return SessionFusionReport(
        ok=scored,
        status=fused.status,
        algorithm_version=fused.algorithm_version,
        alert_level=fused.alert_level,
        alert_source=fused.alert_source,
        fall_decision=snap.fall.decision.value,
        vitals_decision=snap.vitals.decision.value,
        n_samples=snap.window.n_samples,
        n_raw_fetched=snap.window.n_raw_fetched,
        duration_s=snap.window.duration_s,
        protocol_ok=snap.window.protocol_ok,
        median_hr=snap.physio.hr_bpm,
        median_spo2=snap.physio.spo2_percent,
        median_temp=snap.temperature.t_core_est_c,
        iqr_hr=snap.physio.iqr_hr,
        iqr_spo2=snap.physio.iqr_spo2,
        iqr_temp=snap.temperature.iqr_c,
        hr_score=fused.hr_score,
        spo2_score=fused.spo2_score,
        temp_score=fused.temp_score,
        subset_total=fused.subset_total,
        max_component=fused.max_component,
        completeness=fused.completeness,
        max_subset=fused.max_subset,
        n_components=fused.n_components,
        ppg_valid=fused.ppg_valid,
        temp_status=fused.temp_status,
        sqi_level=snap.motion.level.value,
        rms_dyn_g=snap.motion.rms_dyn_g,
        motion_passed=fused.motion_passed,
        smv_peak_g=snap.fall.smv_peak_g,
        reasons=fused.reasons,
        warning=fused.warning,
        tier=fused.tier,
        tier_source=fused.tier_source,
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    if os.getenv("FUSION_ONCE", "").strip() in {"1", "true", "yes"}:
        print(json.dumps(asdict(run_once()), indent=2, default=str))
        return
    interval = float(os.getenv("FUSION_INTERVAL_S", str(DEFAULT_INTERVAL_S)))
    LOGGER.info("Fusion worker %s watching %s", ALGORITHM_VERSION, sqlite_path())
    while True:
        try:
            LOGGER.info("%s", json.dumps(asdict(run_once()), default=str))
        except FileNotFoundError as exc:
            LOGGER.warning("%s — waiting for ingest buffer", exc)
        except Exception:
            LOGGER.exception("fusion tick failed")
        time.sleep(interval)


if __name__ == "__main__":
    main()
