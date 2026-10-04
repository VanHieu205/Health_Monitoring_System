"""Kiosk measurement protocol: settle, acquire, plausibility filter, robust stats.

Reads the SQLite buffer written by ``mqtt_subscriber`` (Phase 1). Default
table/columns match ``sensor_raw_data`` (``ax``, ``ay``, ``az``). Optional
``temp`` / ``acc_*`` names are used when present.

This module does **not** produce a clinical score. It only builds a
protocol-compliant acquire window or explains why the session is invalid.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median, quantiles
from typing import Sequence

DEFAULT_TABLE = "sensor_raw_data"
DEFAULT_SETTLE_SECONDS = 10
DEFAULT_ACQUIRE_SECONDS = 45
# Adult pulse-ox / ECG plausibility (ISO 80601-2-61 operating range is
# device-specific; these bounds only drop physically impossible packets).
DEFAULT_HR_MIN = 30.0
DEFAULT_HR_MAX = 220.0
DEFAULT_SPO2_MIN = 70.0
DEFAULT_SPO2_MAX = 100.0
DEFAULT_TEMP_MIN_C = 32.0
DEFAULT_TEMP_MAX_C = 43.0
DEFAULT_MIN_VALID_HR = 30
DEFAULT_MIN_VALID_SPO2 = 30
DEFAULT_MIN_IMU = 30

DEFAULT_WINDOW_SECONDS = DEFAULT_SETTLE_SECONDS + DEFAULT_ACQUIRE_SECONDS


@dataclass(frozen=True)
class SessionWindow:
    """Acquire-phase samples after settle discard, plus robust summaries."""

    timestamps: list[int]
    hr: list[float]
    spo2: list[float]
    acc_x: list[float]
    acc_y: list[float]
    acc_z: list[float]
    temp: list[float] = field(default_factory=list)
    hr_valid: list[float] = field(default_factory=list)
    spo2_valid: list[float] = field(default_factory=list)
    temp_valid: list[float] = field(default_factory=list)
    median_hr: float | None = None
    median_spo2: float | None = None
    median_temp: float | None = None
    iqr_hr: float | None = None
    iqr_spo2: float | None = None
    mean_hr: float | None = None
    mean_spo2: float | None = None
    mean_temp: float | None = None
    n_raw_fetched: int = 0
    duration_s: float = 0.0
    settle_seconds: int = DEFAULT_SETTLE_SECONDS
    acquire_seconds: int = DEFAULT_ACQUIRE_SECONDS
    protocol_ok: bool = False
    protocol_reasons: tuple[str, ...] = ()
    table_name: str = DEFAULT_TABLE
    has_temperature_column: bool = False

    @property
    def n_samples(self) -> int:
        return len(self.timestamps)

    @property
    def is_empty(self) -> bool:
        return self.n_samples == 0


class SlidingWindowExtractor:
    """Load settle+acquire rows and keep only the acquire segment."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        table: str = DEFAULT_TABLE,
        settle_seconds: int = DEFAULT_SETTLE_SECONDS,
        acquire_seconds: int = DEFAULT_ACQUIRE_SECONDS,
        hr_min: float = DEFAULT_HR_MIN,
        hr_max: float = DEFAULT_HR_MAX,
        spo2_min: float = DEFAULT_SPO2_MIN,
        spo2_max: float = DEFAULT_SPO2_MAX,
        temp_min_c: float = DEFAULT_TEMP_MIN_C,
        temp_max_c: float = DEFAULT_TEMP_MAX_C,
        min_valid_hr: int = DEFAULT_MIN_VALID_HR,
        min_valid_spo2: int = DEFAULT_MIN_VALID_SPO2,
        min_imu: int = DEFAULT_MIN_IMU,
    ) -> None:
        if settle_seconds < 0 or acquire_seconds <= 0:
            raise ValueError("settle_seconds >= 0 and acquire_seconds > 0 required")
        self.db_path = Path(db_path)
        self.table = table
        self.settle_seconds = settle_seconds
        self.acquire_seconds = acquire_seconds
        self.window_seconds = settle_seconds + acquire_seconds
        self.hr_min = hr_min
        self.hr_max = hr_max
        self.spo2_min = spo2_min
        self.spo2_max = spo2_max
        self.temp_min_c = temp_min_c
        self.temp_max_c = temp_max_c
        self.min_valid_hr = min_valid_hr
        self.min_valid_spo2 = min_valid_spo2
        self.min_imu = min_imu

    def fetch(self, *, now_unix: int | None = None) -> SessionWindow:
        """Return acquire samples ending at ``t_end``.

        ``t_end`` is ``now_unix`` when given; otherwise ``max(timestamp)`` so
        offline buffers still form a session. Settle samples in
        ``(t_end - settle - acquire, t_end - acquire]`` are discarded
        (probe placement / PPG lock). Scoring uses
        ``(t_end - acquire, t_end]`` only.
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"SQLite buffer not found: {self.db_path}")

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            columns = self._column_names(conn)
            mapping = self._map_columns(columns)
            t_end = now_unix if now_unix is not None else self._latest_timestamp(conn)
            if t_end is None:
                return self._empty(has_temperature=mapping["temp"] is not None)

            t_start = t_end - self.window_seconds
            sql = self._select_sql(mapping)
            rows = conn.execute(sql, (t_start, t_end)).fetchall()

        return self._to_window(rows, mapping, t_end=t_end)

    def _column_names(self, conn: sqlite3.Connection) -> set[str]:
        quoted = _quote_ident(self.table)
        info = conn.execute(f"PRAGMA table_info({quoted})").fetchall()
        if not info:
            raise ValueError(f"Table {self.table!r} does not exist in {self.db_path}")
        return {str(row["name"]) for row in info}

    def _latest_timestamp(self, conn: sqlite3.Connection) -> int | None:
        quoted = _quote_ident(self.table)
        row = conn.execute(f"SELECT MAX(timestamp) AS t FROM {quoted}").fetchone()
        if row is None or row["t"] is None:
            return None
        return int(row["t"])

    def _select_sql(self, mapping: dict[str, str | None]) -> str:
        quoted = _quote_ident(self.table)
        temp_expr = (
            _quote_ident(mapping["temp"])
            if mapping["temp"]
            else "NULL"
        )
        return (
            f"SELECT timestamp AS timestamp, "
            f"{_quote_ident(mapping['hr'])} AS hr, "
            f"{_quote_ident(mapping['spo2'])} AS spo2, "
            f"{temp_expr} AS temp, "
            f"{_quote_ident(mapping['acc_x'])} AS acc_x, "
            f"{_quote_ident(mapping['acc_y'])} AS acc_y, "
            f"{_quote_ident(mapping['acc_z'])} AS acc_z "
            f"FROM {quoted} "
            f"WHERE timestamp > ? AND timestamp <= ? "
            f"ORDER BY timestamp ASC"
        )

    def _map_columns(self, columns: set[str]) -> dict[str, str | None]:
        def pick(*names: str) -> str | None:
            for name in names:
                if name in columns:
                    return name
            return None

        hr = pick("hr")
        spo2 = pick("spo2")
        acc_x = pick("acc_x", "ax")
        acc_y = pick("acc_y", "ay")
        acc_z = pick("acc_z", "az")
        missing = [
            label
            for label, value in (
                ("hr", hr),
                ("spo2", spo2),
                ("acc_x|ax", acc_x),
                ("acc_y|ay", acc_y),
                ("acc_z|az", acc_z),
            )
            if value is None
        ]
        if "timestamp" not in columns or missing:
            raise ValueError(
                f"Table {self.table!r} is missing required columns: "
                f"{['timestamp'] if 'timestamp' not in columns else []}{missing}"
            )
        return {
            "hr": hr,
            "spo2": spo2,
            "temp": pick("temp"),
            "acc_x": acc_x,
            "acc_y": acc_y,
            "acc_z": acc_z,
        }

    def _to_window(
        self,
        rows: Sequence[sqlite3.Row],
        mapping: dict[str, str | None],
        *,
        t_end: int,
    ) -> SessionWindow:
        has_temp = mapping["temp"] is not None
        t_acquire_start = t_end - self.acquire_seconds
        n_raw = len(rows)

        timestamps: list[int] = []
        hr: list[float] = []
        spo2: list[float] = []
        acc_x: list[float] = []
        acc_y: list[float] = []
        acc_z: list[float] = []
        temp: list[float] = []

        for row in rows:
            ts = int(row["timestamp"])
            if ts <= t_acquire_start:
                continue
            timestamps.append(ts)
            hr.append(float(row["hr"]))
            spo2.append(float(row["spo2"]))
            acc_x.append(float(row["acc_x"]))
            acc_y.append(float(row["acc_y"]))
            acc_z.append(float(row["acc_z"]))
            if has_temp and row["temp"] is not None:
                temp.append(float(row["temp"]))

        hr_valid = [v for v in hr if self.hr_min <= v <= self.hr_max]
        spo2_valid = [v for v in spo2 if self.spo2_min <= v <= self.spo2_max]
        temp_valid = [v for v in temp if self.temp_min_c <= v <= self.temp_max_c]

        duration_s = 0.0
        if timestamps:
            duration_s = float(timestamps[-1] - timestamps[0])

        reasons: list[str] = []
        if len(hr_valid) < self.min_valid_hr:
            reasons.append(
                f"insufficient_valid_hr:{len(hr_valid)}<{self.min_valid_hr}"
            )
        if len(spo2_valid) < self.min_valid_spo2:
            reasons.append(
                f"insufficient_valid_spo2:{len(spo2_valid)}<{self.min_valid_spo2}"
            )
        if len(timestamps) < self.min_imu:
            reasons.append(f"insufficient_imu:{len(timestamps)}<{self.min_imu}")
        min_duration = max(1.0, 0.8 * self.acquire_seconds)
        if duration_s + 1e-9 < min_duration:
            reasons.append(f"acquire_too_short:{duration_s:.1f}s<{min_duration:.0f}s")

        return SessionWindow(
            timestamps=timestamps,
            hr=hr,
            spo2=spo2,
            acc_x=acc_x,
            acc_y=acc_y,
            acc_z=acc_z,
            temp=temp,
            hr_valid=hr_valid,
            spo2_valid=spo2_valid,
            temp_valid=temp_valid,
            median_hr=_median(hr_valid),
            median_spo2=_median(spo2_valid),
            median_temp=_median(temp_valid),
            iqr_hr=_iqr(hr_valid),
            iqr_spo2=_iqr(spo2_valid),
            mean_hr=_mean(hr_valid),
            mean_spo2=_mean(spo2_valid),
            mean_temp=_mean(temp_valid),
            n_raw_fetched=n_raw,
            duration_s=duration_s,
            settle_seconds=self.settle_seconds,
            acquire_seconds=self.acquire_seconds,
            protocol_ok=len(reasons) == 0,
            protocol_reasons=tuple(reasons),
            table_name=self.table,
            has_temperature_column=has_temp,
        )

    def _empty(self, *, has_temperature: bool) -> SessionWindow:
        return SessionWindow(
            timestamps=[],
            hr=[],
            spo2=[],
            acc_x=[],
            acc_y=[],
            acc_z=[],
            temp=[],
            n_raw_fetched=0,
            protocol_ok=False,
            protocol_reasons=("empty_buffer",),
            settle_seconds=self.settle_seconds,
            acquire_seconds=self.acquire_seconds,
            table_name=self.table,
            has_temperature_column=has_temperature,
        )


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return float(median(values))


def _iqr(values: Sequence[float]) -> float | None:
    if len(values) < 4:
        return None
    qs = quantiles(values, n=4, method="inclusive")
    return float(qs[2] - qs[0])


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'
