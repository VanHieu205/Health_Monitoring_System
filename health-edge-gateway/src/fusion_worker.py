"""Session worker: protocol → SQI → NEWS2 subset. Shares SQLite only.

Independent of ``mqtt_subscriber``: this process never opens MQTT and
never writes sensor rows.

TinyML is **not** used in ``subset_total``. Set ``TINYML_P_PHYSIO`` only
to log an unvalidated research stub beside the NEWS2 subset.
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

from algorithms.fusion import DecisionFusion, FusionResult
from algorithms.motion_gate import MotionGateResult, MotionQualityGate
from algorithms.news2_subset import ALGORITHM_VERSION
from algorithms.physio_rule import PhysioNews2Engine, PhysioNews2Result
from algorithms.sliding_win import SessionWindow, SlidingWindowExtractor
from algorithms.temp_rule import TemperatureNews2Result, TemperatureRuleEngine

LOGGER = logging.getLogger("fusion_worker")

GATEWAY_ROOT = SRC_DIR.parent
DEFAULT_DB_PATH = GATEWAY_ROOT / "data" / "local_buffer.db"
DEFAULT_TABLE = "sensor_raw_data"
DEFAULT_INTERVAL_S = 10.0


@dataclass(frozen=True)
class WorkerConfig:
    db_path: Path
    table: str
    settle_seconds: int
    acquire_seconds: int
    interval_seconds: float
    rms_pass_g: float
    rms_fail_g: float
    lsb_per_g: float
    core_offset_c: float
    require_temperature: bool
    tinyml_p_physio: float | None


@dataclass(frozen=True)
class SessionFusionReport:
    """JSON snapshot of one protocol evaluation (not a diagnosis)."""

    ok: bool
    status: str
    algorithm_version: str
    message: str
    n_samples: int
    n_raw_fetched: int
    duration_s: float
    protocol_ok: bool
    median_hr: float | None
    median_spo2: float | None
    median_temp: float | None
    iqr_hr: float | None
    iqr_spo2: float | None
    hr_score: int | None
    spo2_score: int | None
    temp_score: int | None
    subset_total: int | None
    max_subset: int | None
    n_components: int
    sqi_level: str | None
    rms_dyn_g: float | None
    motion_passed: bool | None
    reasons: tuple[str, ...]
    warning: str
    temperature_missing: bool
    tinyml_p_physio_unvalidated: float | None


class FusionWorker:
    """Orchestrate extractor → SQI → NEWS2 vitals → fail-closed fusion."""

    def __init__(self, config: WorkerConfig) -> None:
        self.config = config
        self.extractor = SlidingWindowExtractor(
            config.db_path,
            table=config.table,
            settle_seconds=config.settle_seconds,
            acquire_seconds=config.acquire_seconds,
        )
        self.motion_gate = MotionQualityGate(
            rms_pass_g=config.rms_pass_g,
            rms_fail_g=config.rms_fail_g,
            lsb_per_g=config.lsb_per_g,
        )
        self.physio = PhysioNews2Engine()
        self.temp_engine = TemperatureRuleEngine(
            core_offset_c=config.core_offset_c,
        )
        self.fusion = DecisionFusion(
            require_temperature=config.require_temperature,
        )

    def run_once(self) -> SessionFusionReport:
        window = self.extractor.fetch()
        motion = self.motion_gate.evaluate(window)
        physio = self.physio.evaluate(window)
        temperature = self.temp_engine.evaluate(window)
        fused = self.fusion.fuse(
            window=window,
            motion=motion,
            physio=physio,
            temperature=temperature,
        )
        return _report(window, fused, motion, physio, temperature, self.config)

    def run_forever(self) -> None:
        LOGGER.info(
            "Fusion worker %s watching %s (settle=%ss acquire=%ss period=%ss)",
            ALGORITHM_VERSION,
            self.config.db_path,
            self.config.settle_seconds,
            self.config.acquire_seconds,
            self.config.interval_seconds,
        )
        while True:
            try:
                report = self.run_once()
                LOGGER.info("%s", json.dumps(asdict(report), default=str))
            except FileNotFoundError as exc:
                LOGGER.warning("%s — waiting for Phase 1 buffer", exc)
            except Exception:
                LOGGER.exception("fusion tick failed")
            time.sleep(self.config.interval_seconds)


def _report(
    window: SessionWindow,
    fused: FusionResult,
    motion: MotionGateResult,
    physio: PhysioNews2Result,
    temperature: TemperatureNews2Result,
    config: WorkerConfig,
) -> SessionFusionReport:
    ok = fused.status == "scored"
    return SessionFusionReport(
        ok=ok,
        status=fused.status,
        algorithm_version=fused.algorithm_version,
        message=fused.status,
        n_samples=window.n_samples,
        n_raw_fetched=window.n_raw_fetched,
        duration_s=window.duration_s,
        protocol_ok=window.protocol_ok,
        median_hr=physio.hr_bpm,
        median_spo2=physio.spo2_percent,
        median_temp=temperature.t_core_est_c,
        iqr_hr=physio.iqr_hr,
        iqr_spo2=physio.iqr_spo2,
        hr_score=fused.hr_score,
        spo2_score=fused.spo2_score,
        temp_score=fused.temp_score,
        subset_total=fused.subset_total,
        max_subset=fused.max_subset,
        n_components=fused.n_components,
        sqi_level=fused.sqi_level,
        rms_dyn_g=motion.rms_dyn_g,
        motion_passed=fused.motion_passed,
        reasons=fused.reasons,
        warning=fused.warning,
        temperature_missing=temperature.missing,
        tinyml_p_physio_unvalidated=config.tinyml_p_physio,
    )


def load_config_from_env() -> WorkerConfig:
    db_path = sqlite_path()

    tinyml_raw = os.getenv("TINYML_P_PHYSIO", "").strip()
    tinyml: float | None
    if tinyml_raw.lower() in {"", "none", "off"}:
        tinyml = None
    else:
        tinyml = float(tinyml_raw)

    require_temp = os.getenv("REQUIRE_TEMPERATURE", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    return WorkerConfig(
        db_path=db_path,
        table=os.getenv("SENSOR_TABLE", sensor_table()),
        settle_seconds=int(os.getenv("SETTLE_SECONDS", "10")),
        acquire_seconds=int(os.getenv("ACQUIRE_SECONDS", "45")),
        interval_seconds=float(
            os.getenv("FUSION_INTERVAL_S", str(DEFAULT_INTERVAL_S))
        ),
        rms_pass_g=float(os.getenv("RMS_PASS_G", "0.05")),
        rms_fail_g=float(os.getenv("RMS_FAIL_G", "0.12")),
        lsb_per_g=float(os.getenv("MPU_LSB_PER_G", "16384")),
        core_offset_c=float(os.getenv("TEMP_CORE_OFFSET_C", "0.0")),
        require_temperature=require_temp,
        tinyml_p_physio=tinyml,
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    worker = FusionWorker(load_config_from_env())
    if os.getenv("FUSION_ONCE", "").strip() in {"1", "true", "yes"}:
        report = worker.run_once()
        print(json.dumps(asdict(report), indent=2, default=str))
        return
    worker.run_forever()


if __name__ == "__main__":
    main()
