"""Local training entry used by the FL client (one architecture per call)."""

from __future__ import annotations

from pathlib import Path

from federated_learning.training.config import TrainConfig
from federated_learning.training.pipeline import run_all, run_pipeline


def train_architecture(
    architecture: str,
    *,
    data_dir: str | Path | None = None,
    artifact_dir: str | Path = "artifacts/fl",
    epochs: int = 8,
    n_subjects: int = 8,
    tune: bool = True,
    seed: int = 42,
    use_synthetic_if_missing: bool = True,
) -> dict:
    cfg = TrainConfig(
        architecture=architecture,
        seed=seed,
        data_dir=Path(data_dir) if data_dir else None,
        artifact_dir=Path(artifact_dir),
        use_synthetic_if_missing=use_synthetic_if_missing,
        n_subjects=n_subjects,
        epochs=epochs,
        tune=tune,
    )
    return run_pipeline(cfg)


def train_all(**kwargs) -> dict:
    data_dir = kwargs.pop("data_dir", None)
    artifact_dir = kwargs.pop("artifact_dir", "artifacts/fl")
    cfg = TrainConfig(
        architecture="arch.snn",
        data_dir=Path(data_dir) if data_dir else None,
        artifact_dir=Path(artifact_dir),
        **kwargs,
    )
    return run_all(cfg)
