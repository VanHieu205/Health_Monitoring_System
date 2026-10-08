"""Thin MQTT JSON publisher used by all edge services."""

from __future__ import annotations

import json
import logging
from typing import Any

import paho.mqtt.client as mqtt

from common.config import mqtt_broker, mqtt_port

LOGGER = logging.getLogger("edge.bus")


def publish_json(topic: str, payload: dict[str, Any]) -> None:
    client = mqtt.Client()
    try:
        client.connect(mqtt_broker(), mqtt_port(), 10)
        client.publish(topic, json.dumps(payload, default=str), qos=1)
        client.disconnect()
    except Exception:
        LOGGER.warning("MQTT publish to %s failed (alert still valid locally)", topic)
