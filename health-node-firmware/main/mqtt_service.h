#ifndef MQTT_SERVICE_H
#define MQTT_SERVICE_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

bool init_wifi_and_mqtt(const char *ssid, const char *pass, const char *broker_uri);
bool mqtt_is_connected(void);
bool mqtt_publish_mock_data(int hr, int spo2, int16_t ax, int16_t ay, int16_t az, int battery);

#ifdef __cplusplus
}
#endif

#endif // MQTT_SERVICE_H
