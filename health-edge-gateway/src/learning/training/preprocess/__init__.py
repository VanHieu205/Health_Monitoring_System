from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Split:
    X_train: np.ndarray
    y_train: np.ndarray
    X_val: np.ndarray
    y_val: np.ndarray
    X_test: np.ndarray
    y_test: np.ndarray
    subject_train: np.ndarray
    subject_val: np.ndarray
    subject_test: np.ndarray
    X_raw_train: np.ndarray | None = None
    X_raw_val: np.ndarray | None = None
    X_raw_test: np.ndarray | None = None


def subject_holdout(corpus: dict, *, seed: int, val_ratio: float = 0.15) -> Split:
    """Split by subject, never by window (no leakage).

    WEDA ids (young U01–U14, elder U21+) are stratified so val and test
    both keep young subjects. Other datasets keep a plain subject shuffle.
    """
    subjects = np.unique(corpus["subject"])
    rng = np.random.default_rng(seed)
    n = len(subjects)
    n_test = max(1, n // 5)
    n_val = max(1, int(round((n - n_test) * val_ratio))) if n - n_test > 2 else 1
    if n_test + n_val >= n:
        n_val = 1
        n_test = min(n_test, max(1, n - 2))
    groups = _weda_age_groups(subjects)
    if groups is None:
        order = subjects.copy()
        rng.shuffle(order)
        test_s = set(order[:n_test])
        val_s = set(order[n_test : n_test + n_val])
        train_s = set(order[n_test + n_val :])
    else:
        young, old = groups
        test_s, val_s, train_s = _stratified_pools(young, old, n_test, n_val, rng)
    if not train_s:
        train_s = set(subjects[n_test + n_val - 1 :])
        val_s = set(subjects[n_test : n_test + n_val - 1]) or {subjects[0]}

    def take(pool: set) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None]:
        names = {str(s) for s in pool}
        mask = np.array([str(s) in names for s in corpus["subject"]], dtype=bool)
        raw = corpus["X_raw"][mask] if "X_raw" in corpus else None
        return corpus["X"][mask], corpus["y"][mask], corpus["subject"][mask], raw

    xt, yt, st, rt = take(train_s)
    xv, yv, sv, rv = take(val_s)
    xe, ye, se, re = take(test_s)
    return Split(xt, yt, xv, yv, xe, ye, st, sv, se, rt, rv, re)


def _weda_age_groups(subjects: np.ndarray) -> tuple[list, list] | None:
    young, old = [], []
    for subject in subjects.tolist():
        text = str(subject)
        if len(text) < 2 or text[0] not in "Uu" or not text[1:].isdigit():
            return None
        n = int(text[1:])
        if 1 <= n <= 14:
            young.append(subject)
        elif n >= 21:
            old.append(subject)
        else:
            return None
    if not young or not old:
        return None
    return young, old


def _stratified_pools(young: list, old: list, n_test: int, n_val: int, rng: np.random.Generator):
    young = list(young)
    old = list(old)
    rng.shuffle(young)
    rng.shuffle(old)
    ty, to = _quota(len(young), len(old), n_test)
    vy, vo = _quota(len(young) - ty, len(old) - to, n_val)
    # Leave at least one training subject when the pool is large enough.
    if len(young) + len(old) - (ty + to + vy + vo) < 1 and vy + vo > 1:
        if vy > 1:
            vy -= 1
        elif vo > 1:
            vo -= 1
    test = young[:ty] + old[:to]
    val = young[ty : ty + vy] + old[to : to + vo]
    train = young[ty + vy :] + old[to + vo :]
    return set(test), set(val), set(train)


def _quota(n_young: int, n_old: int, n_take: int) -> tuple[int, int]:
    """Proportional take, with at least one young subject when both sides exist."""
    n_take = min(n_take, n_young + n_old)
    if n_take <= 0:
        return 0, 0
    if n_young == 0:
        return 0, n_take
    if n_old == 0:
        return n_take, 0
    y = int(round(n_take * n_young / (n_young + n_old)))
    y = min(max(y, 1), n_young, n_take)
    o = n_take - y
    if o > n_old:
        o = n_old
        y = n_take - o
    return y, o


def class_weights(y: np.ndarray, n_classes: int) -> np.ndarray:
    """Square root of inverse frequency.

    Full inverse frequency makes overlapping classes collapse onto the
    smaller one. The square root keeps a milder tilt toward rare classes.
    """
    counts = np.bincount(y.astype(int), minlength=n_classes).astype(np.float64)
    w = np.ones(n_classes, dtype=np.float64)
    present = counts > 0
    n_present = int(present.sum())
    if n_present:
        w[present] = np.sqrt(counts[present].sum() / (n_present * counts[present]))
        w[~present] = 0.0
    return w.astype(np.float32)
