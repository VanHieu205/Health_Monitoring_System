"""IMU window → 12 spike channels plus posture and gait rhythm.

Accel channels use a threshold in g. Gyro channels use a threshold in deg/s.
A step that jumps many thresholds emits that many spikes and advances the
reference by the same amount, so impact amplitude is not collapsed to 1.

Four extra channels were gravity and one rhythm. The input is now gravity
xyz, an SMV crossing rate, and a gyro crossing rate at 30 deg/s.
"""

from __future__ import annotations

import numpy as np

# 0.05 g fires on roughly half of real WEDA steps without saturating.
# 10 deg/s is above the Fitbit 0.1 rad/s quantization step (~5.7 deg/s).
DEFAULT_DELTA_ACC_G = 0.05
DEFAULT_DELTA_GYR_DPS = 10.0
# Upper bound for the gait band. The value used in a run is fit on train elders.
RHYTHM_BAND_G = 0.15
GYRO_RHYTHM_DPS = 30.0
CONTEXT_FS = 50.0


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


def encode_motion(
    windows: np.ndarray,
    delta: float | tuple[float, float] = DEFAULT_DELTA_ACC_G,
    rhythm_band: float = RHYTHM_BAND_G,
) -> np.ndarray:
    """(N, T, 6) IMU → (N, T, 17) spikes, gravity, SMV rhythm, gyro rhythm."""
    raw = np.asarray(windows, dtype=np.float32)
    spikes = delta_encode(raw, delta)
    context = _context_channels(raw, rhythm_band)
    tiled = np.repeat(context[:, None, :], raw.shape[1], axis=1)
    return np.concatenate([spikes, tiled], axis=-1)


def smv_peak(windows: np.ndarray) -> np.ndarray:
    acc = np.asarray(windows, dtype=np.float64)[..., :3]
    return np.sqrt((acc ** 2).sum(axis=-1)).max(axis=-1)


def fit_rhythm_band(windows: np.ndarray | None, y: np.ndarray, subjects: np.ndarray) -> float:
    """SMV crossing level from training elders' walk windows.

    Uses the lower end of their step size so a quiet gait still counts as
    walking. Never raised above 0.15 g, and never taken from val or test.
    """
    from learning.training.config import SNN_WALK_INDEX

    if windows is None or len(np.asarray(y)) == 0:
        return RHYTHM_BAND_G
    keep = []
    for index, sid in enumerate(np.asarray(subjects)):
        text = str(sid)
        if len(text) < 2 or text[0] not in "Uu" or not text[1:].isdigit():
            continue
        if int(text[1:]) < 21 or int(y[index]) != SNN_WALK_INDEX:
            continue
        keep.append(index)
    if not keep:
        return RHYTHM_BAND_G
    acc = np.asarray(windows, dtype=np.float64)[keep][..., :3]
    smv = np.sqrt((acc ** 2).sum(axis=-1))
    centered = smv - np.median(smv, axis=1, keepdims=True)
    excursion = np.quantile(centered, 0.9, axis=1)
    band = float(np.quantile(excursion, 0.2))
    return float(np.clip(band, 0.05, RHYTHM_BAND_G))


def _context_channels(windows: np.ndarray, rhythm_band: float) -> np.ndarray:
    acc = windows[..., :3].astype(np.float64)
    gyro = windows[..., 3:].astype(np.float64)
    gravity = acc.mean(axis=1)
    duration = max(windows.shape[1] / CONTEXT_FS, 1e-6)
    smv_hz = _crossing_rate(np.sqrt((acc ** 2).sum(axis=-1)), rhythm_band, duration)
    gyro_mag = np.sqrt((gyro ** 2).sum(axis=-1))
    gyro_hz = _crossing_rate(gyro_mag, GYRO_RHYTHM_DPS, duration)
    return np.concatenate([gravity, smv_hz[:, None], gyro_hz[:, None]], axis=1).astype(np.float32)


def _crossing_rate(signal: np.ndarray, band: float, duration: float) -> np.ndarray:
    baseline = np.median(signal, axis=1, keepdims=True)
    centered = signal - baseline
    upward = (centered[:, :-1] < band) & (centered[:, 1:] >= band)
    return upward.sum(axis=1) / duration


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
    spikes = encode_motion(x, (d_acc, d_gyr))
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
