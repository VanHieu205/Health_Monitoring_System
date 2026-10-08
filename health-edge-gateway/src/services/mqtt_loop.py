"""Shared MQTT subscribe loop for event-driven edge services."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt

from common.config import mqtt_broker, mqtt_port

LOGGER = logging.getLogger("edge.mqtt")
OnJson = Callable[[str, dict[str, Any]], None]


def device_id_from_topic(topic: str) -> str:
    parts = topic.split("/")
    if len(parts) >= 2 and parts[0] in {"watch", "gateway"}:
        return parts[1]
    return ""


def run_subscriber(name: str, topics: list[str], on_json: OnJson) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    client = mqtt.Client()

    def _on_message(_c, _u, msg) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            if not isinstance(payload, dict):
                LOGGER.warning("%s ignored non-object on %s", name, msg.topic)
                return
            on_json(msg.topic, payload)
        except Exception:
            LOGGER.exception("%s failed on %s", name, msg.topic)

    client.on_message = _on_message
    client.connect(mqtt_broker(), mqtt_port(), 60)
    client.subscribe([(topic, 1) for topic in topics])
    LOGGER.info("%s listening %s", name, topics)
    client.loop_forever()
