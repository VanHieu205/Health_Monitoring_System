import struct
import time
import random
import paho.mqtt.client as mqtt

# Cấu hình MQTT Broker (kết nối vào localhost do cổng 1883 đã được Docker expose)
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC = "sensor/raw/device_001"

client = mqtt.Client()

def generate_18byte_packet():
    """Đóng gói dữ liệu giả lập thành cấu trúc nhị phân 18 bytes"""
    timestamp = int(time.time())      # uint32 (4 bytes)
    hr = random.randint(60, 100)      # uint16 (2 bytes)
    spo2 = random.randint(95, 100)    # uint8 (1 byte)
    ax = random.randint(-1000, 1000)  # int16 (2 bytes)
    ay = random.randint(-1000, 1000)  # int16 (2 bytes)
    az = random.randint(-1000, 1000)  # int16 (2 bytes)
    event_flag = 0                    # uint8 (1 byte)
    battery = random.randint(20, 100) # uint8 (1 byte)
    padding = b'\x00' * 3             # 3 bytes padding để tròn 18 bytes
    
    # Định dạng struct: I(uint32), H(uint16), B(uint8), h(int16)
    packet = struct.pack('<I H B h h h B B', timestamp, hr, spo2, ax, ay, az, event_flag, battery) + padding
    return packet

if __name__ == "__main__":
    print(f"Đang kết nối tới MQTT Broker tại {MQTT_BROKER}:{MQTT_PORT}...")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        print("Kết nối thành công! Bắt đầu phát luồng dữ liệu 18-bytes...")
        while True:
            payload = generate_18byte_packet()
            client.publish(TOPIC, payload)
            print(f"Đã gửi [18 bytes]: {payload.hex()}")
            time.sleep(1) # Tần số 1Hz
    except ConnectionRefusedError:
        print("Lỗi: Không thể kết nối. Hãy đảm bảo Docker chứa 'local-mqtt' đang chạy (docker compose ps).")
    except KeyboardInterrupt:
        print("\nĐã dừng giả lập.")
        client.disconnect()