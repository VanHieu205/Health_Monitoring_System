#ifndef BLE_PACKET_18BYTE_H
#define BLE_PACKET_18BYTE_H

#include <stdint.h>

// Binary Packed Struct exactly 18-bytes for optimal EDP & radio wake-up
#pragma pack(push, 1)
typedef struct {
    uint32_t timestamp;    // 4 bytes: Unix epoch timestamp
    uint16_t heart_rate;   // 2 bytes: Heart rate (bpm * 10)
    uint8_t  spo2;         // 1 byte:  SpO2 percentage (0-100)
    int16_t  ax;           // 2 bytes: IMU Accel X (scaled)
    int16_t  ay;           // 2 bytes: IMU Accel Y (scaled)
    int16_t  az;           // 2 bytes: IMU Accel Z (scaled)
    uint8_t  event_flag;   // 1 byte:  Bit 0: Fall, Bit 1: Anomaly, Bit 2-7: Reserved
    uint8_t  battery;      // 1 byte:  Battery level percentage (0-100)
    uint16_t checksum;     // 2 bytes: CRC16/Checksum
    uint8_t  reserved;     // 1 byte:  Padding / Alignment
} ble_health_packet_t;     // Total: 4 + 2 + 1 + 2 + 2 + 2 + 1 + 1 + 2 + 1 = 18 bytes
#pragma pack(pop)

#endif // BLE_PACKET_18BYTE_H
