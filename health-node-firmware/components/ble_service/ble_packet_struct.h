#ifndef BLE_PACKET_STRUCT_H
#define BLE_PACKET_STRUCT_H
#include "../../components/ble_service/ble_packet_struct.h"
#include <stdint.h>

#pragma pack(push, 1)
typedef struct {
    uint32_t timestamp;
    uint16_t heart_rate;
    uint8_t  spo2;
    int16_t  ax, ay, az;
    uint8_t  event_flag;
    uint8_t  battery;
    uint16_t checksum;
    uint8_t  reserved;
} ble_health_packet_t;
#pragma pack(pop)
#endif
