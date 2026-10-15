"""Small validation grids. Thresholds are chosen on val only."""

from __future__ import annotations

from copy import deepcopy

import numpy as np

from federated_learning.training.config import TrainConfig
from federated_learning.training.metrics import auroc, binary_f1_at
from federated_learning.training.preprocess.snn import delta_encode
from federated_learning.training.train_loop import eval_snn, fit_binary, fit_snn


def tune_snn(split, cfg: TrainConfig) -> dict:
    # One (lr, beta, delta) triple per trial so delta is chosen on val
    # without multiplying the existing trial budget.
    grid = [
        {"lr": 1e-3, "beta": 0.9, "delta_acc": 0.05, "delta_gyr": 6.0},
        {"lr": 5e-4, "beta": 0.85, "delta_acc": 0.10, "delta_gyr": 20.0},
        {"lr": 2e-3, "beta": 0.95, "delta_acc": 0.17, "delta_gyr": 40.0},
        {"lr": 1e-3, "beta": 0.8, "delta_acc": 0.34, "delta_gyr": 20.0},
    ][: cfg.max_tune_trials]
    best, best_score = grid[0], -1.0
    trials = []
    has_raw = getattr(split, "X_raw_train", None) is not None
    print(f"[arch.snn tune] {len(grid)} trials, {max(3, cfg.epochs // 2)} epochs each", flush=True)
    for index, trial in enumerate(grid, start=1):
        x_train, x_val = split.X_train, split.X_val
        if has_raw:
            spec = (trial["delta_acc"], trial["delta_gyr"])
            x_train = delta_encode(split.X_raw_train, spec)
            x_val = delta_encode(split.X_raw_val, spec)
        tag = (
            f"arch.snn tune {index}/{len(grid)} "
            f"lr={trial['lr']:g} beta={trial['beta']:g} "
            f"d_acc={trial['delta_acc']:g} d_gyr={trial['delta_gyr']:g}"
        )
        print(f"[{tag}] start", flush=True)
        fit = fit_snn(
            x_train, split.y_train,
            epochs=max(3, cfg.epochs // 2),
            batch_size=cfg.batch_size,
            lr=trial["lr"],
            beta=trial["beta"],
            device=cfg.device,
            x_val=x_val,
            y_val=split.y_val,
            log_tag=tag,
        )
        metrics = eval_snn(fit.model, x_val, split.y_val, cfg.device)
        score = 0.5 * metrics["f1_macro"] + 0.5 * metrics["sensitivity_fall_like"]
        print(
            f"[{tag}] score={score:.4f}  val_f1={metrics['f1_macro']:.4f}  "
            f"val_se_fall={metrics['sensitivity_fall_like']:.4f}",
            flush=True,
        )
        trials.append({**trial, **{k: v for k, v in metrics.items() if k != "f1_per_class"}, "score": score})
        if score > best_score:
            best, best_score = trial, score
    return {"best": best, "trials": trials}


def tune_binary(split, cfg: TrainConfig, *, hidden_grid: list[tuple[int, ...]]) -> dict:
    lrs = [1e-3, 5e-4]
    grid = []
    for hidden in hidden_grid:
        for lr in lrs:
            grid.append({"hidden": hidden, "lr": lr})
    grid = grid[: cfg.max_tune_trials]
    best, best_score = grid[0], -1.0
    trials = []
    for trial in grid:
        fit = fit_binary(
            split.X_train, split.y_train,
            hidden=trial["hidden"],
            epochs=max(4, cfg.epochs // 2),
            batch_size=cfg.batch_size,
            lr=trial["lr"],
            weight_decay=cfg.weight_decay,
            device=cfg.device,
            x_val=split.X_val,
            y_val=split.y_val,
        )
        from federated_learning.training.train_loop import eval_binary

        metrics = eval_binary(fit.model, split.X_val, split.y_val, cfg.device)
        score = metrics["auroc"]
        trials.append({**trial, "hidden": list(trial["hidden"]), "auroc": score, "f1": metrics["f1_positive"]})
        if score > best_score:
            best, best_score = deepcopy(trial), score
    return {"best": {**best, "hidden": list(best["hidden"])}, "trials": trials}


def choose_fall_threshold(model, x_val: np.ndarray, y_val: np.ndarray, device: str) -> float:
    """Pick P(fall) on val by fall-class F1, then sensitivity.

    The 0.5·F1-macro + 0.5·sensitivity score used for epochs prefers a very
    low threshold that labels most walking as a fall.
    """
    import torch

    from federated_learning.training.config import SNN_FALL_INDEX
    from federated_learning.training.metrics import f1_per_class, sensitivity
    from federated_learning.training.train_loop import predict_snn

    model.eval()
    with torch.no_grad():
        logits = model(torch.tensor(x_val, device=device)).cpu().numpy()
    y = np.asarray(y_val)
    n_classes = int(logits.shape[1])
    best_tau, best_key = 0.5, None
    for tau in np.linspace(0.05, 0.95, 37):
        pred = predict_snn(logits, float(tau))
        f1_fall = f1_per_class(y, pred, n_classes)[SNN_FALL_INDEX]
        se = sensitivity(y, pred, SNN_FALL_INDEX)
        key = (f1_fall, se, -abs(float(tau) - 0.5))
        if best_key is None or key > best_key:
            best_tau, best_key = float(tau), key
    return best_tau


def choose_threshold(y_val: np.ndarray, scores: np.ndarray) -> float:
    best_tau, best_f1 = 0.5, -1.0
    for tau in np.linspace(0.25, 0.8, 12):
        pred = np.asarray(scores) >= tau
        if pred.all() or not pred.any():
            continue
        f1 = binary_f1_at(y_val, scores, float(tau))
        if f1 > best_f1:
            best_tau, best_f1 = float(tau), f1
    return best_tau


def unused_auroc(*args):
    return auroc(*args)
