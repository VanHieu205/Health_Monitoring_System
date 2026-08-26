# BLE Packet Simulator for 18-byte struct
import struct
import time

def generate_packet(hr=75, spo2=98, ax=0, ay=0, az=16384, event=0, battery=90):
    ts = int(time.time())
    checksum = 0xA55A
    reserved = 0
    return struct.pack("<IHh3hBBHB", ts, int(hr*10), spo2, ax, ay, az, event, battery, checksum, reserved)
