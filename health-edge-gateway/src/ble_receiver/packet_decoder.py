# Unpack 18-byte binary struct to dictionaryimport struct
import struct

def decode_18byte_packet(hex_string):
    """Giải mã chuỗi Hex 18-bytes về dạng Dictionary chứa dữ liệu y tế"""
    try:
        # Chuyển chuỗi Hex về dạng bytes
        packet = bytes.fromhex(hex_string)
        
        # Cấu trúc 15 bytes dữ liệu (3 bytes cuối là padding không cần giải mã)
        # < : Little-endian
        # I : uint32 (Timestamp)
        # H : uint16 (Nhịp tim)
        # B : uint8  (SpO2)
        # h : int16  (Gia tốc ax, ay, az)
        # B : uint8  (Event Flag, Battery)
        unpacked_data = struct.unpack('<I H B h h h B B', packet[:15])
        
        decoded = {
            "timestamp": unpacked_data[0],
            "hr": unpacked_data[1],
            "spo2": unpacked_data[2],
            "ax": unpacked_data[3],
            "ay": unpacked_data[4],
            "az": unpacked_data[5],
            "event_flag": unpacked_data[6],
            "battery": unpacked_data[7]
        }
        return decoded
    except Exception as e:
        print(f"Lỗi giải mã: {e}")
        return None

# Đoạn test nhanh nếu chạy độc lập file này
if __name__ == "__main__":
    test_hex = "4268ae6a3c0061f0010400e5fc0038000000"
    print(decode_18byte_packet(test_hex))