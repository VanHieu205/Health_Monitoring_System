"""Encode local weights / diffs for one architecture only."""

from __future__ import annotations

from typing import Any

import torch


ALLOWED_KEYS = frozenset(
    {"architecture", "n_samples", "model_version", "weights", "delta"}
)


def flatten_state(state: dict[str, torch.Tensor]) -> dict[str, list[float]]:
    return {key: tensor.detach().cpu().float().reshape(-1).tolist() for key, tensor in state.items()}


def encode_update(
    *,
    architecture: str,
    state_dict: dict[str, torch.Tensor],
    n_samples: int,
    global_state: dict[str, torch.Tensor] | None = None,
    model_version: str = "local",
) -> dict[str, Any]:
    if global_state is None:
        payload = {"weights": flatten_state(state_dict)}
    else:
        delta = {
            key: (state_dict[key] - global_state[key]).detach().cpu().float().reshape(-1).tolist()
            for key in state_dict
        }
        payload = {"delta": delta}
    return {
        "architecture": architecture,
        "n_samples": int(n_samples),
        "model_version": model_version,
        **payload,
    }
