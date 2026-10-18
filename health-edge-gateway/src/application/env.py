"""Build SessionPipeline from process environment."""

from __future__ import annotations

import os

from application.session_pipeline import PipelineConfig, SessionPipeline


def pipeline_from_env() -> SessionPipeline:
    require_temp = os.getenv("REQUIRE_TEMPERATURE", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    return SessionPipeline(
        PipelineConfig(
            rms_pass_g=float(os.getenv("RMS_PASS_G", "0.05")),
            rms_fail_g=float(os.getenv("RMS_FAIL_G", "0.12")),
            lsb_per_g=float(os.getenv("MPU_LSB_PER_G", "2048")),
            max_iqr_hr_bpm=float(os.getenv("PPG_MAX_IQR_HR_BPM", "10")),
            max_iqr_spo2_pct=float(os.getenv("PPG_MAX_IQR_SPO2_PCT", "2")),
            core_offset_c=float(os.getenv("TEMP_CORE_OFFSET_C", "0.0")),
            min_temp_samples=int(os.getenv("TEMP_MIN_SAMPLES", "10")),
            max_iqr_temp_c=float(os.getenv("TEMP_MAX_IQR_C", "0.3")),
            require_temperature=require_temp,
            review_sum=int(os.getenv("TIER_REVIEW_SUM", "5")),
            smv_impact_g=float(os.getenv("FALL_SMV_IMPACT_G", "2.5")),
        )
    )
