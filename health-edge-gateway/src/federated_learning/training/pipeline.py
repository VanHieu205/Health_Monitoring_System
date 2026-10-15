"""EDA → preprocess → subject split → tune (val) → train → evaluate (test)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import torch

from algorithms.news2 import (
    ALGORITHM_VERSION,
    FL_ARCHITECTURE_SNN,
    FL_ARCHITECTURE_SQI,
    FL_ARCHITECTURE_TREND,
)
from federated_learning.training.config import TrainConfig
from federated_learning.training.data.loaders import load_snn, load_sqi, load_trend
from federated_learning.training.eda import run_eda
from federated_learning.training.evaluate import evaluate_snn, evaluate_sqi, evaluate_trend
from federated_learning.training.preprocess import Split, subject_holdout
from federated_learning.training.preprocess.snn import (
    DEFAULT_DELTA_ACC_G,
    DEFAULT_DELTA_GYR_DPS,
    delta_encode,
    prepare_snn,
)
from federated_learning.training.preprocess.tabular import Standardizer
from federated_learning.training.seed import set_seed
from federated_learning.training.train_loop import eval_binary, fit_binary, fit_snn
from federated_learning.training.tune import choose_fall_threshold, choose_threshold, tune_binary, tune_snn


def run_pipeline(cfg: TrainConfig) -> dict:
    set_seed(cfg.seed)
    out = cfg.out_dir()
    if cfg.architecture == FL_ARCHITECTURE_SNN:
        report = _run_snn(cfg, out)
    elif cfg.architecture == FL_ARCHITECTURE_SQI:
        report = _run_sqi(cfg, out)
    elif cfg.architecture == FL_ARCHITECTURE_TREND:
        report = _run_trend(cfg, out)
    else:
        raise ValueError(f"unknown architecture {cfg.architecture}")
    report["algorithm_version"] = ALGORITHM_VERSION
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    (out / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def run_all(base: TrainConfig) -> dict:
    reports = {}
    for arch in (FL_ARCHITECTURE_SNN, FL_ARCHITECTURE_SQI, FL_ARCHITECTURE_TREND):
        cfg = TrainConfig(
            architecture=arch,
            seed=base.seed,
            data_dir=base.data_dir,
            artifact_dir=base.artifact_dir,
            use_synthetic_if_missing=base.use_synthetic_if_missing,
            n_subjects=base.n_subjects,
            epochs=base.epochs,
            batch_size=base.batch_size,
            tune=base.tune,
            max_tune_trials=base.max_tune_trials,
            device=base.device,
        )
        reports[arch] = run_pipeline(cfg)
    return reports


def _run_snn(cfg: TrainConfig, out) -> dict:
    raw = _remap_weda_labels(load_snn(
        cfg.data_dir, n_subjects=cfg.n_subjects, seed=cfg.seed,
        synthetic_ok=cfg.use_synthetic_if_missing,
    ))
    prepared = prepare_snn(
        raw,
        delta_acc=float(cfg.extra.get("delta_acc", DEFAULT_DELTA_ACC_G)),
        delta_gyr=float(cfg.extra.get("delta_gyr", DEFAULT_DELTA_GYR_DPS)),
    )
    _log(
        f"[arch.snn] loaded source={raw.get('source')} windows={len(raw['y'])} "
        f"subjects={len(set(raw['subject'].tolist()))}"
    )
    eda = run_eda(cfg.architecture, prepared, out)
    _log(f"[arch.snn] eda class_counts={eda.get('class_counts')}")
    split = subject_holdout(prepared, seed=cfg.seed)
    _log(
        f"[arch.snn] split train={len(split.y_train)} val={len(split.y_val)} "
        f"test={len(split.y_test)}"
    )
    tuned = tune_snn(split, cfg) if cfg.tune else {"best": {"lr": cfg.lr, "beta": 0.9}, "trials": []}
    best = tuned["best"]
    _log(f"[arch.snn] selected hparams {best}")
    split = _encode_split(
        split,
        float(best.get("delta_acc", prepared["delta_acc"])),
        float(best.get("delta_gyr", prepared["delta_gyr"])),
    )
    _log(f"[arch.snn train] start epochs={cfg.epochs} lr={best['lr']} beta={best['beta']}")
    fit = fit_snn(
        split.X_train, split.y_train,
        epochs=cfg.epochs,
        batch_size=cfg.batch_size,
        lr=best["lr"],
        beta=best["beta"],
        device=cfg.device,
        x_val=split.X_val,
        y_val=split.y_val,
        log_tag="arch.snn train",
    )
    tau = choose_fall_threshold(fit.model, split.X_val, split.y_val, cfg.device)
    best = {**best, "fall_tau": tau}
    test = evaluate_snn(fit.model, split.X_test, split.y_test, cfg.device, tau=tau)
    _log(
        f"[arch.snn test] acc={test['accuracy']:.4f}  f1={test['f1_macro']:.4f}  "
        f"se_fall={test['sensitivity_fall_like']:.4f}  tau={tau:.3f}  n={test['n_test']}"
    )
    ckpt = out / "model.pt"
    torch.save(
        {
            "architecture": cfg.architecture,
            "state_dict": fit.best_state,
            "hparams": best,
            "n_train": fit.n_train,
        },
        ckpt,
    )
    return {
        "architecture": cfg.architecture,
        "source": raw.get("source"),
        "eda": eda,
        "split": _split_info(split),
        "tune": tuned,
        "history": fit.history,
        "test": test,
        "checkpoint": str(ckpt),
        "n_samples": fit.n_train,
    }


def _run_tabular(cfg: TrainConfig, out, *, load_fn, hidden_grid, kind: str) -> dict:
    raw = load_fn(
        cfg.data_dir, n_subjects=cfg.n_subjects, seed=cfg.seed,
        synthetic_ok=cfg.use_synthetic_if_missing,
    )
    eda = run_eda(cfg.architecture, raw, out)
    split = subject_holdout(raw, seed=cfg.seed)
    scaler = Standardizer.fit(split.X_train)
    split.X_train[:] = scaler.transform(split.X_train)  # type: ignore[index]
    x_val = scaler.transform(split.X_val)
    x_test = scaler.transform(split.X_test)
    # rebuild split-like namespace
    class _S:
        pass

    s = _S()
    s.X_train, s.y_train = split.X_train, split.y_train
    s.X_val, s.y_val = x_val, split.y_val
    s.X_test, s.y_test = x_test, split.y_test
    tuned = tune_binary(s, cfg, hidden_grid=hidden_grid) if cfg.tune else {
        "best": {"hidden": list(hidden_grid[0]), "lr": cfg.lr},
        "trials": [],
    }
    best = tuned["best"]
    hidden = tuple(best["hidden"])
    fit = fit_binary(
        s.X_train, s.y_train,
        hidden=hidden,
        epochs=cfg.epochs,
        batch_size=cfg.batch_size,
        lr=best["lr"],
        weight_decay=cfg.weight_decay,
        device=cfg.device,
        x_val=s.X_val,
        y_val=s.y_val,
    )
    val_scores = np.asarray(eval_binary(fit.model, s.X_val, s.y_val, cfg.device)["scores"])
    tau = choose_threshold(s.y_val, val_scores)
    if kind == "sqi":
        test = evaluate_sqi(fit.model, s.X_test, s.y_test, cfg.device, tau)
    else:
        test = evaluate_trend(fit.model, s.X_test, s.y_test, cfg.device, tau)
    ckpt = out / "model.pt"
    torch.save(
        {
            "architecture": cfg.architecture,
            "state_dict": fit.best_state,
            "hparams": {**best, "tau": tau},
            "scaler": scaler.state_dict(),
            "n_train": fit.n_train,
        },
        ckpt,
    )
    return {
        "architecture": cfg.architecture,
        "source": raw.get("source"),
        "eda": eda,
        "split": _split_info(split),
        "tune": tuned,
        "threshold": tau,
        "history": fit.history,
        "test": test,
        "checkpoint": str(ckpt),
        "n_samples": fit.n_train,
    }


def _run_sqi(cfg: TrainConfig, out) -> dict:
    return _run_tabular(cfg, out, load_fn=load_sqi, hidden_grid=[(16,), (32,), (16, 8)], kind="sqi")


def _run_trend(cfg: TrainConfig, out) -> dict:
    return _run_tabular(cfg, out, load_fn=load_trend, hidden_grid=[(32, 16), (24, 12), (16,)], kind="trend")


def _remap_weda_labels(corpus: dict) -> dict:
    """windows.npz stores sit_stand=1, walk=2, fall_like=3. Train ids are 0,1,2."""
    y = np.asarray(corpus["y"])
    if y.size == 0 or int(y.min()) < 1 or int(y.max()) > 3:
        return corpus
    out = dict(corpus)
    out["y"] = (y - 1).astype(np.int64)
    return out


def _encode_split(split: Split, delta_acc: float, delta_gyr: float) -> Split:
    if split.X_raw_train is None:
        return split
    spec = (delta_acc, delta_gyr)
    return Split(
        delta_encode(split.X_raw_train, spec),
        split.y_train,
        delta_encode(split.X_raw_val, spec),
        split.y_val,
        delta_encode(split.X_raw_test, spec),
        split.y_test,
        split.subject_train,
        split.subject_val,
        split.subject_test,
        split.X_raw_train,
        split.X_raw_val,
        split.X_raw_test,
    )


def _log(message: str) -> None:
    print(message, flush=True)


def _split_info(split) -> dict:
    return {
        "n_train": int(len(split.y_train)),
        "n_val": int(len(split.y_val)),
        "n_test": int(len(split.y_test)),
        "subjects_train": sorted(set(split.subject_train.tolist())),
        "subjects_val": sorted(set(split.subject_val.tolist())),
        "subjects_test": sorted(set(split.subject_test.tolist())),
        "rule": "split_by_subject_no_window_leakage",
    }
