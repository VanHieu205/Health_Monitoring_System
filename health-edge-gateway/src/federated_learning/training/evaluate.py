from __future__ import annotations

import numpy as np
import torch

from federated_learning.training.config import SNN_CLASSES
from federated_learning.training.metrics import (
    accuracy,
    auprc,
    auroc,
    binary_f1_at,
    confusion,
    f1_per_class,
    sensitivity,
)
from federated_learning.training.train_loop import eval_binary, eval_snn, predict_snn


def evaluate_snn(model, x_test, y_test, device: str, *, tau: float | None = None) -> dict:
    metrics = eval_snn(model, x_test, y_test, device, tau=tau)
    with torch.no_grad():
        logits = model(torch.tensor(x_test, device=device)).cpu().numpy()
    pred = predict_snn(logits, tau)
    metrics["confusion"] = confusion(y_test, pred, len(SNN_CLASSES))
    metrics["classes"] = list(SNN_CLASSES)
    metrics["n_test"] = int(len(y_test))
    if tau is not None:
        metrics["fall_tau"] = tau
    return metrics


def evaluate_sqi(model, x_test, y_test, device: str, tau: float) -> dict:
    raw = eval_binary(model, x_test, y_test, device)
    scores = np.asarray(raw["scores"])
    pred = (scores >= tau).astype(int)
    return {
        "auroc": raw["auroc"],
        "auprc": auprc(y_test, scores),
        "accuracy": accuracy(y_test, pred),
        "f1_good": f1_per_class(y_test, pred, 2)[1],
        "tau": tau,
        "yield": float(pred.mean()),
        "n_test": int(len(y_test)),
        "n_true_good": int(y_test.sum()),
    }


def evaluate_trend(model, x_test, y_test, device: str, tau: float) -> dict:
    raw = eval_binary(model, x_test, y_test, device)
    scores = np.asarray(raw["scores"])
    pred = (scores >= tau).astype(int)
    l_now = x_test[:, -1]
    l_trend = np.where(pred == 1, np.minimum(l_now + 1, 2), 0)
    return {
        "auroc": raw["auroc"],
        "auprc": auprc(y_test, scores),
        "f1_rise": binary_f1_at(y_test, scores, tau),
        "tau_det": tau,
        "max_l_trend": int(l_trend.max()) if len(l_trend) else 0,
        "l_trend_never_emergency": bool((l_trend <= 2).all()),
        "n_test": int(len(y_test)),
        "positive_rate": float(y_test.mean()) if len(y_test) else 0.0,
    }
