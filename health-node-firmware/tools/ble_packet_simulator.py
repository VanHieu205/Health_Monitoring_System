# # BLE Packet Simulator for 18-byte struct
# import struct
# import time

# def generate_packet(hr=75, spo2=98, ax=0, ay=0, az=16384, event=0, battery=90):
#     ts = int(time.time())
#     checksum = 0xA55A
#     reserved = 0
#     return struct.pack("<IHh3hBBHB", ts, int(hr*10), spo2, ax, ay, az, event, battery, checksum, reserved)


import struct
import time
import random
import paho.mqtt.client as mqtt

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC = "sensor/raw/device_001"

client = mqtt.Client()
client.connect(MQTT_BROKER, MQTT_PORT, 60)

def generate_18byte_packet():
    timestamp = int(time.time()) # uint32 (4 bytes)
    hr = random.randint(60, 100) # uint16 (2 bytes)
    spo2 = random.randint(95, 100) # uint8 (1 byte)
    ax = random.randint(-1000, 1000) # int16 (2 bytes)
    ay = random.randint(-1000, 1000) # int16 (2 bytes)
    az = random.randint(-1000, 1000) # int16 (2 bytes)
    event_flag = 0 # uint8 (1 byte)
    battery = random.randint(20, 100) # uint8 (1 byte)
    padding = b'\x00' * 3 # 3 bytes padding để đủ 18 bytes
    
    # Định dạng struct: I (uint32), H (uint16), B (uint8), h (int16)
    packet = struct.pack('<I H B h h h B B', timestamp, hr, spo2, ax, ay, az, event_flag, battery) + padding
    return packet

if __name__ == "__main__":
    print("Bắt đầu giả lập phát BLE packet 18-byte...")
    try:
        while True:
            payload = generate_18byte_packet()
            client.publish(TOPIC, payload)
            print(f"Đã gửi: {payload.hex()}")
            time.sleep(1) # Tần số 1Hz
    except KeyboardInterrupt:
        client.disconnect()