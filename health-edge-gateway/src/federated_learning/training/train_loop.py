from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from federated_learning.training.config import SNN_CLASSES, SNN_FALL_INDEX
from federated_learning.training.metrics import accuracy, auroc, f1_per_class, sensitivity
from federated_learning.training.models.snn_lif import MotionSNN
from federated_learning.training.models.tabular_mlp import BinaryMLP
from federated_learning.training.preprocess import class_weights


@dataclass
class FitResult:
    model: nn.Module
    history: list[dict]
    best_state: dict
    n_train: int


def fit_snn(
    x: np.ndarray,
    y: np.ndarray,
    *,
    epochs: int,
    batch_size: int,
    lr: float,
    beta: float,
    device: str,
    x_val: np.ndarray | None = None,
    y_val: np.ndarray | None = None,
    log_tag: str = "snn",
) -> FitResult:
    n_classes = len(SNN_CLASSES)
    model = MotionSNN(n_out=n_classes, beta=beta).to(device)
    weights = torch.tensor(class_weights(y, n_classes), device=device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.CrossEntropyLoss(weight=weights)
    loader = _loader(x, y, batch_size, seq=True)
    history = []
    best, best_score = None, -1.0
    for epoch in range(1, epochs + 1):
        model.train()
        total = 0.0
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()
            total += float(loss.detach()) * len(yb)
        row = {"epoch": epoch, "train_loss": total / max(1, len(y))}
        if x_val is not None:
            metrics = eval_snn(model, x_val, y_val, device)
            row.update({f"val_{k}": v for k, v in metrics.items()})
            score = 0.5 * metrics["f1_macro"] + 0.5 * metrics["sensitivity_fall_like"]
            improved = score >= best_score
            if improved:
                best_score = score
                best = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            _log_epoch(log_tag, epoch, epochs, row, best=improved)
        else:
            _log_epoch(log_tag, epoch, epochs, row, best=False)
        history.append(row)
    if best is not None:
        model.load_state_dict(best)
    return FitResult(model, history, {k: v.cpu() for k, v in model.state_dict().items()}, len(y))


def fit_binary(
    x: np.ndarray,
    y: np.ndarray,
    *,
    hidden: tuple[int, ...],
    epochs: int,
    batch_size: int,
    lr: float,
    weight_decay: float,
    device: str,
    x_val: np.ndarray | None = None,
    y_val: np.ndarray | None = None,
    log_tag: str = "binary",
) -> FitResult:
    model = BinaryMLP(x.shape[1], hidden=hidden).to(device)
    pos = max(1, int((y == 1).sum()))
    neg = max(1, int((y == 0).sum()))
    pos_weight = torch.tensor([neg / pos], device=device)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    loader = _loader(x, y, batch_size, seq=False)
    history = []
    best, best_score = None, -1.0
    for epoch in range(1, epochs + 1):
        model.train()
        total = 0.0
        for xb, yb in loader:
            xb = xb.to(device)
            yb = yb.to(device).float()
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
            total += float(loss.detach()) * len(yb)
        row = {"epoch": epoch, "train_loss": total / max(1, len(y))}
        if x_val is not None:
            metrics = eval_binary(model, x_val, y_val, device)
            row.update({f"val_{k}": v for k, v in metrics.items()})
            improved = metrics["auroc"] >= best_score
            if improved:
                best_score = metrics["auroc"]
                best = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            _log_epoch(log_tag, epoch, epochs, row, best=improved)
        else:
            _log_epoch(log_tag, epoch, epochs, row, best=False)
        history.append(row)
    if best is not None:
        model.load_state_dict(best)
    return FitResult(model, history, {k: v.cpu() for k, v in model.state_dict().items()}, len(y))


def predict_snn(logits: np.ndarray, tau: float | None = None) -> np.ndarray:
    """Argmax, or fall iff P(fall) >= tau and otherwise the best other class."""
    logits = np.asarray(logits, dtype=np.float64)
    if tau is None:
        return logits.argmax(axis=1).astype(np.int64)
    scores = _fall_probability(logits)
    others = logits.copy()
    others[:, SNN_FALL_INDEX] = -np.inf
    backup = others.argmax(axis=1)
    return np.where(scores >= tau, SNN_FALL_INDEX, backup).astype(np.int64)


def _fall_probability(logits: np.ndarray) -> np.ndarray:
    z = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(z)
    prob = exp / exp.sum(axis=1, keepdims=True)
    return prob[:, SNN_FALL_INDEX]


@torch.no_grad()
def eval_snn(
    model: nn.Module,
    x: np.ndarray,
    y: np.ndarray,
    device: str,
    *,
    tau: float | None = None,
) -> dict:
    model.eval()
    logits = model(torch.tensor(x, device=device)).cpu().numpy()
    pred = predict_snn(logits, tau)
    n_classes = len(SNN_CLASSES)
    f1s = f1_per_class(y, pred, n_classes)
    present = [(np.asarray(y) == k).any() for k in range(n_classes)]
    f1_macro = float(np.mean([f1s[k] for k in range(n_classes) if present[k]])) if any(present) else 0.0
    return {
        "accuracy": accuracy(y, pred),
        "f1_macro": f1_macro,
        "f1_per_class": f1s,
        "sensitivity_fall_like": sensitivity(y, pred, SNN_FALL_INDEX),
    }


@torch.no_grad()
def eval_binary(model: nn.Module, x: np.ndarray, y: np.ndarray, device: str) -> dict:
    model.eval()
    logits = model(torch.tensor(x, device=device)).cpu().numpy()
    scores = 1.0 / (1.0 + np.exp(-np.clip(logits, -20, 20)))
    pred = (scores >= 0.5).astype(int)
    return {
        "accuracy": accuracy(y, pred),
        "auroc": auroc(y, scores),
        "f1_positive": f1_per_class(y, pred, 2)[1],
        "scores": scores.tolist(),
    }


def _log_epoch(tag: str, epoch: int, epochs: int, row: dict, *, best: bool) -> None:
    parts = [f"[{tag}] epoch {epoch}/{epochs}", f"loss={row['train_loss']:.4f}"]
    if "val_accuracy" in row:
        parts.append(f"val_acc={row['val_accuracy']:.4f}")
    if "val_f1_macro" in row:
        parts.append(f"val_f1={row['val_f1_macro']:.4f}")
    if "val_sensitivity_fall_like" in row:
        parts.append(f"val_se_fall={row['val_sensitivity_fall_like']:.4f}")
    if "val_f1_per_class" in row:
        named = ",".join(
            f"{name}:{score:.2f}" for name, score in zip(SNN_CLASSES, row["val_f1_per_class"], strict=False)
        )
        parts.append(f"f1=[{named}]")
    if "val_auroc" in row:
        parts.append(f"val_auroc={row['val_auroc']:.4f}")
    if "val_f1_positive" in row:
        parts.append(f"val_f1_pos={row['val_f1_positive']:.4f}")
    if best:
        parts.append("*best")
    print("  ".join(parts), flush=True)


def _loader(x: np.ndarray, y: np.ndarray, batch_size: int, *, seq: bool) -> DataLoader:
    xt = torch.tensor(x, dtype=torch.float32)
    yt = torch.tensor(y, dtype=torch.long)
    return DataLoader(TensorDataset(xt, yt), batch_size=batch_size, shuffle=True)
