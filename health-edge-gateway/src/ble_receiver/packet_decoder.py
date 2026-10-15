# Unpack an 18-byte binary struct to a dictionary.
import struct


def decode_18byte_packet(hex_string):
    """Decode an 18-byte hex packet into a vital-sign dictionary."""
    try:
        packet = bytes.fromhex(hex_string)

        # First 15 bytes are payload; last 3 bytes are unused padding.
        # < : little-endian
        # I : uint32 (timestamp)
        # H : uint16 (heart rate)
        # B : uint8  (SpO2)
        # h : int16  (accel ax, ay, az)
        # B : uint8  (event flag, battery)
        unpacked_data = struct.unpack("<I H B h h h B B", packet[:15])

        decoded = {
            "timestamp": unpacked_data[0],
            "hr": unpacked_data[1],
            "spo2": unpacked_data[2],
            "ax": unpacked_data[3],
            "ay": unpacked_data[4],
            "az": unpacked_data[5],
            "event_flag": unpacked_data[6],
            "battery": unpacked_data[7],
        }
        return decoded
    except Exception as e:
        print(f"Decode error: {e}")
        return None


if __name__ == "__main__":
    test_hex = "4268ae6a3c0061f0010400e5fc0038000000"
    print(decode_18byte_packet(test_hex))