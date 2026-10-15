"""IMU window → 12 spike channels (delta modulator, PDF eq. 1).

Accel channels use a threshold in g. Gyro channels use a threshold in deg/s.
A step that jumps many thresholds emits that many spikes and advances the
reference by the same amount, so impact amplitude is not collapsed to 1.
"""

from __future__ import annotations

import numpy as np

# 0.05 g fires on roughly half of real WEDA steps without saturating.
# 10 deg/s is above the Fitbit 0.1 rad/s quantization step (~5.7 deg/s).
DEFAULT_DELTA_ACC_G = 0.05
DEFAULT_DELTA_GYR_DPS = 10.0


def clip_imu_g(windows: np.ndarray, acc_clip: float = 16.0, gyr_clip: float = 2000.0) -> np.ndarray:
    """Clip accel in g and gyro in deg/s (MPU6050 full scale)."""
    out = np.array(windows, dtype=np.float32, copy=True)
    out[..., :3] = np.clip(out[..., :3], -acc_clip, acc_clip)
    out[..., 3:] = np.clip(out[..., 3:], -gyr_clip, gyr_clip)
    return out


def delta_encode(windows: np.ndarray, delta: float | tuple[float, float] = DEFAULT_DELTA_ACC_G) -> np.ndarray:
    """windows: (N, T, 6) → spike counts (N, T, 12).

    ``delta`` is one threshold for every channel, or ``(delta_acc_g, delta_gyr_deg_s)``.
    """
    x = np.asarray(windows, dtype=np.float32)
    n, t, c = x.shape
    step = _delta_per_channel(delta, c)
    spikes = np.zeros((n, t, c * 2), dtype=np.float32)
    ref = x[:, 0, :].copy()
    for i in range(t):
        cur = x[:, i, :]
        diff = cur - ref
        npos = np.floor(np.maximum(diff, 0.0) / step)
        nneg = np.floor(np.maximum(-diff, 0.0) / step)
        spikes[:, i, 0::2] = npos
        spikes[:, i, 1::2] = nneg
        ref = ref + (npos - nneg) * step
    return spikes


def prepare_snn(
    corpus: dict,
    *,
    delta: float | tuple[float, float] | None = None,
    delta_acc: float | None = None,
    delta_gyr: float | None = None,
) -> dict:
    d_acc = DEFAULT_DELTA_ACC_G if delta_acc is None else float(delta_acc)
    d_gyr = DEFAULT_DELTA_GYR_DPS if delta_gyr is None else float(delta_gyr)
    if isinstance(delta, tuple):
        d_acc, d_gyr = float(delta[0]), float(delta[1])
    elif delta is not None and delta_acc is None:
        d_acc = float(delta)
    x = clip_imu_g(corpus["X"])
    spikes = delta_encode(x, (d_acc, d_gyr))
    out = dict(corpus)
    out["X_raw"] = x
    out["X"] = spikes
    out["delta_acc"] = d_acc
    out["delta_gyr"] = d_gyr
    return out


def _delta_per_channel(delta: float | tuple[float, float], n_chan: int) -> np.ndarray:
    if isinstance(delta, tuple):
        acc, gyr = float(delta[0]), float(delta[1])
        if n_chan != 6:
            raise ValueError(f"paired delta expects 6 IMU channels, got {n_chan}")
        values = np.array([acc, acc, acc, gyr, gyr, gyr], dtype=np.float32)
    else:
        values = np.full(n_chan, float(delta), dtype=np.float32)
    if np.any(values <= 0):
        raise ValueError(f"delta must be positive, got {values}")
    return values
