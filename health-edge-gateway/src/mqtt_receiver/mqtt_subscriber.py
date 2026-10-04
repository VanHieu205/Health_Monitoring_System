# MQTT Subscriber for Raspberry Pi 4 (Receives Mock Health Data from ESP32-C3)
import json
# pyrefly: ignore [missing-import]
import paho.mqtt.client as mqtt

# MQTT Broker Configuration
BROKER_IP = "localhost"   # When running directly on Raspberry Pi (with Mosquitto installed)
BROKER_PORT = 1883
TOPIC_DATA = "health/node/data"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[Raspberry Pi] Connected to MQTT Broker successfully.")
        client.subscribe(TOPIC_DATA)
        print(f"Listening for health data on topic: '{TOPIC_DATA}'...\n")
    else:
        print(f"Failed to connect to MQTT Broker, return code: {rc}")

def on_message(client, userdata, msg):
    try:
        raw_payload = msg.payload.decode('utf-8')
        data = json.loads(raw_payload)

        device_id = data.get("device_id", "Unknown")
        timestamp = data.get("timestamp", 0)
        hr        = data.get("heart_rate", 0)
        spo2      = data.get("spo2", 0)
        imu       = data.get("imu", {})
        battery   = data.get("battery", 0)

        print(f"[MQTT DATA RECEIVED from {device_id}] (timestamp: {timestamp}s):")
        print(f"   Heart Rate : {hr} bpm")
        print(f"   SpO2       : {spo2} %")
        print(f"   IMU Accel  : Ax={imu.get('ax')}, Ay={imu.get('ay')}, Az={imu.get('az')}")
        print(f"   Battery    : {battery} %")
        print("   " + "-" * 40)

        # Future integration: pass data into local AI model inference on Pi 4

    except Exception as e:
        print(f"Error parsing JSON payload: {e} (Payload: {msg.payload})")

def main():
    print("Starting MQTT Health Data Subscriber on Raspberry Pi 4...")
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(BROKER_IP, BROKER_PORT, 60)
        client.loop_forever()
    except ConnectionRefusedError:
        print(f"Connection refused by MQTT Broker at {BROKER_IP}:{BROKER_PORT}")
        print("Please verify Mosquitto service is running on Raspberry Pi: 'sudo systemctl start mosquitto'")
    except KeyboardInterrupt:
        print("\nMQTT Subscriber stopped by user.")

if __name__ == "__main__":
    main()
