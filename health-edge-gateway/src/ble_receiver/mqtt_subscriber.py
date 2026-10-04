from common.config import mqtt_topic
from common.config import mqtt_port
from common.config import mqtt_broker
from common.config import load_gateway_env
import os
import sys

# pyrefly: ignore [missing-import]
from packet_decoder import decode_18byte_packet

# pyrefly: ignore [missing-import]
import paho.mqtt.client as mqtt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# pyrefly: ignore [missing-import]
from local_storage.db_models import SessionLocal, SensorRecord

load_gateway_env()
MQTT_BROKER = mqtt_broker()
MQTT_PORT = mqtt_port()
TOPIC = mqtt_topic()

def on_message(client, userdata, msg):
    hex_payload = msg.payload.hex()
    data = decode_18byte_packet(hex_payload)
    
    if data:
        print(f"\n[+] Nhận gói tin -> Nhịp tim: {data['hr']} bpm | SpO2: {data['spo2']}%")
        
        try:
            db = SessionLocal()
            new_record = SensorRecord(
                timestamp=data['timestamp'],
                hr=data['hr'],
                spo2=data['spo2'],
                ax=data['ax'],
                ay=data['ay'],
                az=data['az'],
                event_flag=data['event_flag'],
                battery=data['battery']
            )
            db.add(new_record)
            db.commit()
            db.close()
            print("    [v] Đã lưu an toàn vào DB Cục bộ (SQLite)")
        except Exception as e:
            print(f"    [x] Lỗi khi lưu DB: {e}")

if __name__ == "__main__":
    client = mqtt.Client()
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.subscribe(TOPIC)
        print(f"Đang lắng nghe dữ liệu từ Topic '{TOPIC}' và kết nối với SQLite...")
        client.loop_forever()
    except ConnectionRefusedError:
        print("Lỗi: Không tìm thấy MQTT Broker.")