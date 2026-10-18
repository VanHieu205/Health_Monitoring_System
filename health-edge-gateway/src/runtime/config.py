"""Load gateway settings from ``.env`` then process environment.

Device/runtime values live in env. NEWS2 cut-points stay in
``domain.news2`` and are not configured here.
"""

from __future__ import annotations

import os
from pathlib import Path

GATEWAY_ROOT = Path(__file__).resolve().parents[2]


def load_gateway_env(env_file: Path | None = None) -> Path | None:
    """Populate ``os.environ`` from a dotenv file without overwriting existing keys."""
    candidates: list[Path] = []
    override = os.getenv("GATEWAY_ENV_FILE", "").strip()
    if env_file is not None:
        candidates.append(Path(env_file))
    elif override:
        candidates.append(Path(override))
    else:
        candidates.append(GATEWAY_ROOT / ".env")
        candidates.append(Path.cwd() / ".env")

    seen: set[Path] = set()
    loaded: Path | None = None
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        _apply_dotenv(resolved)
        loaded = resolved
        break
    return loaded


def _apply_dotenv(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip("'").strip('"')


def mqtt_broker() -> str:
    return os.getenv("MQTT_BROKER", "127.0.0.1")


def mqtt_port() -> int:
    return int(os.getenv("MQTT_PORT", "1883"))


def mqtt_topic() -> str:
    return os.getenv("MQTT_TOPIC", "sensor/raw/#")


def sqlite_path() -> Path:
    raw = os.getenv("SQLITE_PATH", str(GATEWAY_ROOT / "data" / "local_buffer.db"))
    path = Path(raw)
    if not path.is_absolute():
        path = (GATEWAY_ROOT / path).resolve()
    return path


def sqlite_url() -> str:
    return "sqlite:///" + sqlite_path().as_posix()


def sensor_table() -> str:
    return os.getenv("SENSOR_TABLE", "sensor_raw_data")
