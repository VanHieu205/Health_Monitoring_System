from __future__ import annotations

from torch import nn


class BinaryMLP(nn.Module):
    def __init__(self, n_in: int, hidden: tuple[int, ...] = (16,)):
        super().__init__()
        layers: list[nn.Module] = []
        prev = n_in
        for width in hidden:
            layers.extend([nn.Linear(prev, width), nn.ReLU(), nn.Dropout(0.1)])
            prev = width
        layers.append(nn.Linear(prev, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x).squeeze(-1)
