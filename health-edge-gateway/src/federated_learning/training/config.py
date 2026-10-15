"""Training hyperparameters. NEWS2 cut-points are never stored here."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# WEDA has no rest or not_worn samples. An empty logit was winning argmax,
# so the trained head is the three classes that actually appear.
# File labels stay sit_stand=1, walk=2, fall_like=3; training remaps them to 0,1,2.
SNN_CLASSES = ("sit_stand", "walk", "fall_like")
SNN_FALL_INDEX = SNN_CLASSES.index("fall_like")
SQI_FEATURES = ("iqr_hr", "n_beats", "rms_acc_g", "ac_dc", "motion_code")
TREND_FEATURES = (
    "hr_median", "hr_slope", "hr_std",
    "spo2_median", "spo2_slope", "spo2_std",
    "rr_median", "rr_slope", "rr_std",
    "temp_median", "temp_slope", "temp_std",
    "l_news",
)


@dataclass(frozen=True)
class TrainConfig:
    architecture: str
    seed: int = 42
    data_dir: Path | None = None
    artifact_dir: Path = Path("artifacts/fl")
    use_synthetic_if_missing: bool = True
    n_subjects: int = 8
    epochs: int = 8
    batch_size: int = 32
    lr: float = 1e-3
    weight_decay: float = 1e-4
    tune: bool = True
    max_tune_trials: int = 4
    device: str = "cpu"
    extra: dict = field(default_factory=dict)

    def out_dir(self) -> Path:
        path = self.artifact_dir / self.architecture.replace(".", "_")
        path.mkdir(parents=True, exist_ok=True)
        return path
