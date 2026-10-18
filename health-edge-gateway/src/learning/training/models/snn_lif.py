"""17 → 32 LIF → leaky readout.

Input is 12 delta-spike channels, gravity xyz, SMV rhythm, and gyro rhythm.

The hidden layer spikes. The output layer does not: its membrane is summed
over time and used as logits. A spike-count readout tied every class at 0
and argmax then always returned the first class.
"""

from __future__ import annotations

import torch
from torch import nn


class SurrogateSpike(torch.autograd.Function):
    @staticmethod
    def forward(ctx, membrane: torch.Tensor, threshold: float, k: float):
        ctx.save_for_backward(membrane)
        ctx.threshold = threshold
        ctx.k = k
        return (membrane > threshold).to(membrane.dtype)

    @staticmethod
    def backward(ctx, grad_output):
        (membrane,) = ctx.saved_tensors
        denom = (1.0 + ctx.k * (membrane - ctx.threshold).abs()) ** 2
        return grad_output / denom, None, None


class LIFLayer(nn.Module):
    def __init__(self, n_in: int, n_out: int, beta: float = 0.9, threshold: float = 1.0, k: float = 10.0):
        super().__init__()
        self.linear = nn.Linear(n_in, n_out, bias=False)
        nn.init.xavier_uniform_(self.linear.weight, gain=1.0)
        self.beta = beta
        self.threshold = threshold
        self.k = k

    def step(self, spikes_in: torch.Tensor, mem: torch.Tensor, prev_spk: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        mem = self.beta * mem + self.linear(spikes_in) - self.threshold * prev_spk
        spikes = SurrogateSpike.apply(mem, self.threshold, self.k)
        return spikes, mem


class MotionSNN(nn.Module):
    def __init__(self, n_in: int = 17, n_hidden: int = 32, n_out: int = 4, beta: float = 0.9):
        super().__init__()
        self.hidden = LIFLayer(n_in, n_hidden, beta=beta)
        self.output = LIFLayer(n_hidden, n_out, beta=beta)
        self.n_hidden = n_hidden
        self.n_out = n_out

    def forward(self, spikes: torch.Tensor) -> torch.Tensor:
        """spikes: (B, T, n_in) → summed output membrane (B, n_out)."""
        batch, steps, _ = spikes.shape
        mem_h = spikes.new_zeros(batch, self.n_hidden)
        spk_h = spikes.new_zeros(batch, self.n_hidden)
        mem_o = spikes.new_zeros(batch, self.n_out)
        logits = spikes.new_zeros(batch, self.n_out)
        beta = self.output.beta
        for t in range(steps):
            spk_h, mem_h = self.hidden.step(spikes[:, t], mem_h, spk_h)
            mem_o = beta * mem_o + self.output.linear(spk_h)
            logits = logits + mem_o
        return logits
