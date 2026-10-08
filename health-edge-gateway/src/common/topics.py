"""MQTT topics for the hospital NEWS2 gateway (DACN_HuongTrienKhai.pdf)."""

WATCH_ALL = "watch/+/+"
WATCH_PPG = "watch/+/ppg_session"
WATCH_TEMP = "watch/+/temp"
WATCH_MOTION = "watch/+/motion"
WATCH_FALL = "watch/+/fall_candidate"
WATCH_BUTTON = "watch/+/button"
WATCH_HEARTBEAT = "watch/+/heartbeat"

# Legacy 18-byte simulator
WATCH_RAW = "sensor/raw/#"

SIGNAL = "gateway/signal"
NEWS2_DECISION = "gateway/news2/decision"
FALL_DECISION = "gateway/fall/decision"
TREND_DECISION = "gateway/trend/decision"
VITALS_DECISION = NEWS2_DECISION  # old name
NURSE_ALERT = "gateway/alert"
NURSE_ACK = "gateway/ack"
DEVICE_STATUS = "gateway/device"
MANUAL_INPUT = "gateway/manual"
FL_ROUND = "gateway/fl/round"
LOCAL_ALARM = "gateway/local_alarm"


def watch_topic(device_id: str, kind: str) -> str:
    return f"watch/{device_id}/{kind}"
