"""ble_ingest: watch MQTT → SQLite. No clinical scoring."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC))
from sqlalchemy.exc import IntegrityError

from runtime.config import load_gateway_env, mqtt_broker, mqtt_port, mqtt_topic
from contracts.envelope import EnvelopeError, validate_envelope
from contracts.topics import WATCH_ALL
from persistence.db_models import RawEvent, SessionLocal
from ingress.mqtt_subscriber import on_message as on_legacy_binary

load_gateway_env()
LOGGER = logging.getLogger("ingest")


def _store_json(topic: str, payload: dict) -> None:
    envelope = validate_envelope(payload)
    kind = topic.rsplit("/", 1)[-1]
    db = SessionLocal()
    try:
        db.add(
            RawEvent(
                device_id=str(envelope["device_id"]),
                seq=int(envelope["seq"]),
                kind=kind,
                ts_ms=int(envelope["ts_ms"]),
                payload=json.dumps(envelope, default=str),
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        LOGGER.info("duplicate seq device=%s seq=%s", envelope["device_id"], envelope["seq"])
    finally:
        db.close()


def main() -> None:
    import paho.mqtt.client as mqtt

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    client = mqtt.Client()

    def on_message(c, u, msg) -> None:
        if msg.topic.startswith("watch/"):
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
                _store_json(msg.topic, payload)
            except (json.JSONDecodeError, EnvelopeError, KeyError, TypeError, ValueError) as exc:
                LOGGER.warning("drop %s: %s", msg.topic, exc)
            return
        on_legacy_binary(c, u, msg)

    client.on_message = on_message
    client.connect(mqtt_broker(), mqtt_port(), 60)
    client.subscribe([(WATCH_ALL, 1), (mqtt_topic(), 1)])
    LOGGER.info("ingest listening %s and %s", WATCH_ALL, mqtt_topic())
    client.loop_forever()


if __name__ == "__main__":
    main()
