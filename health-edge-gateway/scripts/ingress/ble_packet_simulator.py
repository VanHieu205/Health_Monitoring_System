import struct
import time
import random
import paho.mqtt.client as mqtt

# MQTT broker. Docker Compose publishes port 1883 on localhost.
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC = "sensor/raw/device_001"

client = mqtt.Client()

def generate_18byte_packet():
    """Pack a simulated sample into the legacy 18-byte binary layout."""
    timestamp = int(time.time())      # uint32 (4 bytes)
    hr = random.randint(60, 100)      # uint16 (2 bytes)
    spo2 = random.randint(95, 100)    # uint8 (1 byte)
    ax = random.randint(-1000, 1000)  # int16 (2 bytes)
    ay = random.randint(-1000, 1000)  # int16 (2 bytes)
    az = random.randint(-1000, 1000)  # int16 (2 bytes)
    event_flag = 0                    # uint8 (1 byte)
    battery = random.randint(20, 100) # uint8 (1 byte)
    padding = b'\x00' * 3             # 3 bytes of padding to reach 18 bytes

    # Struct layout: I(uint32), H(uint16), B(uint8), h(int16)
    packet = struct.pack('<I H B h h h B B', timestamp, hr, spo2, ax, ay, az, event_flag, battery) + padding
    return packet

if __name__ == "__main__":
    print(f"Connecting to the MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        print("Connected. Publishing the 18-byte stream...")
        while True:
            payload = generate_18byte_packet()
            client.publish(TOPIC, payload)
            print(f"Sent [18 bytes]: {payload.hex()}")
            time.sleep(1)  # 1 Hz
    except ConnectionRefusedError:
        print("Could not connect. Start the local-mqtt service first (docker compose ps).")
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
        client.disconnect()
