#ifndef APP_CONFIG_H
#define APP_CONFIG_H

// --- WI-FI AND MQTT CONFIGURATION ---
// Configure your local Wi-Fi SSID and Password
#define WIFI_SSID "zzzzz"
#define WIFI_PASSWORD "Aa110305"

// MQTT Broker URI on Raspberry Pi 4 (Mosquitto)
#define MQTT_BROKER_URI "mqtt://192.168.137.185:1883"
#define MQTT_TOPIC_DATA "health/node/data"

// Mock data transmission interval in milliseconds
#define MQTT_PUBLISH_INTERVAL_MS 1000

#endif // APP_CONFIG_H
