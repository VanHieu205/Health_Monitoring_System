from __future__ import annotations

import math

import numpy as np


def accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    return float((y_true == y_pred).mean()) if len(y_true) else 0.0


def f1_per_class(y_true: np.ndarray, y_pred: np.ndarray, n_classes: int) -> list[float]:
    scores = []
    for k in range(n_classes):
        tp = int(((y_true == k) & (y_pred == k)).sum())
        fp = int(((y_true != k) & (y_pred == k)).sum())
        fn = int(((y_true == k) & (y_pred != k)).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        scores.append(0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec))
    return scores


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson interval for k successes in n trials."""
    if n <= 0:
        return None
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    centre = (p + z2 / (2.0 * n)) / den
    half = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def sensitivity(y_true: np.ndarray, y_pred: np.ndarray, positive: int) -> float:
    mask = y_true == positive
    if not mask.any():
        return 0.0
    return float((y_pred[mask] == positive).mean())


def confusion(y_true: np.ndarray, y_pred: np.ndarray, n_classes: int) -> list[list[int]]:
    mat = np.zeros((n_classes, n_classes), dtype=int)
    for t, p in zip(y_true, y_pred, strict=True):
        mat[int(t), int(p)] += 1
    return mat.tolist()


def auroc(y_true: np.ndarray, scores: np.ndarray) -> float:
    y = np.asarray(y_true).astype(int)
    s = np.asarray(scores, dtype=np.float64)
    pos = s[y == 1]
    neg = s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    # Mann–Whitney / Wilcoxon
    order = np.argsort(s)
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, len(s) + 1)
    sum_pos = ranks[y == 1].sum()
    u = sum_pos - len(pos) * (len(pos) + 1) / 2.0
    return float(u / (len(pos) * len(neg)))


def auprc(y_true: np.ndarray, scores: np.ndarray) -> float:
    y = np.asarray(y_true).astype(int)
    s = np.asarray(scores, dtype=np.float64)
    if y.sum() == 0:
        return 0.0
    order = np.argsort(-s)
    y_sorted = y[order]
    tp = np.cumsum(y_sorted)
    fp = np.cumsum(1 - y_sorted)
    prec = tp / np.maximum(tp + fp, 1)
    rec = tp / y.sum()
    rec = np.concatenate([[0.0], rec])
    prec = np.concatenate([[1.0], prec])
    area = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
    return float(area(prec, rec))


def binary_f1_at(y_true: np.ndarray, scores: np.ndarray, tau: float) -> float:
    pred = (np.asarray(scores) >= tau).astype(int)
    return f1_per_class(y_true, pred, 2)[1]
