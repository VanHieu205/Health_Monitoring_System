#include "mqtt_service.h"
#include <string.h>
#include <stdio.h>
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "nvs_flash.h"
#include "mqtt_client.h"
#include "esp_timer.h"
#include "cJSON.h"

static const char *TAG = "MQTT_Service";

static esp_mqtt_client_handle_t s_mqtt_client = NULL;
static bool s_wifi_connected = false;
static bool s_mqtt_connected = false;
static char s_broker_uri[128] = "mqtt://192.168.1.190:1883";

static void mqtt_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data) {
    switch ((esp_mqtt_event_id_t)event_id) {
    case MQTT_EVENT_CONNECTED:
        ESP_LOGI(TAG, "[MQTT] Connected to MQTT Broker successfully.");
        s_mqtt_connected = true;
        break;
    case MQTT_EVENT_DISCONNECTED:
        ESP_LOGW(TAG, "[MQTT] Disconnected from MQTT Broker, reconnecting...");
        s_mqtt_connected = false;
        break;
    case MQTT_EVENT_ERROR:
        ESP_LOGE(TAG, "[MQTT] MQTT Event Error");
        break;
    default:
        break;
    }
}

static void start_mqtt_client(void) {
    if (s_mqtt_client != NULL) {
        esp_mqtt_client_reconnect(s_mqtt_client);
        return;
    }

    esp_mqtt_client_config_t mqtt_cfg = {};
    mqtt_cfg.broker.address.uri = s_broker_uri;

    s_mqtt_client = esp_mqtt_client_init(&mqtt_cfg);
    if (s_mqtt_client == NULL) {
        ESP_LOGE(TAG, "Failed to initialize MQTT client");
        return;
    }

    esp_mqtt_client_register_event(s_mqtt_client, (esp_mqtt_event_id_t)ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    esp_mqtt_client_start(s_mqtt_client);
    ESP_LOGI(TAG, "Connecting to MQTT Broker: %s...", s_broker_uri);
}

static void wifi_event_handler(void *arg, esp_event_base_t event_base, int32_t event_id, void *event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        ESP_LOGI(TAG, "Wi-Fi Station started, connecting...");
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        wifi_event_sta_disconnected_t *disc = (wifi_event_sta_disconnected_t *)event_data;
        s_wifi_connected = false;
        s_mqtt_connected = false;
        ESP_LOGW(TAG, "Wi-Fi disconnected (reason code=%d), reconnecting...", disc ? disc->reason : -1);
        esp_wifi_connect();
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        ESP_LOGI(TAG, "Wi-Fi Connected! IP: " IPSTR, IP2STR(&event->ip_info.ip));
        s_wifi_connected = true;
        start_mqtt_client();
    }
}

bool init_wifi_and_mqtt(const char *ssid, const char *pass, const char *broker_uri) {
    if (broker_uri != NULL && strlen(broker_uri) > 0) {
        strncpy(s_broker_uri, broker_uri, sizeof(s_broker_uri) - 1);
        s_broker_uri[sizeof(s_broker_uri) - 1] = '\0';
    }

    // 1. Initialize NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // 2. Initialize TCP/IP and Event Loop
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    // 3. Initialize Wi-Fi
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL, NULL));

    wifi_config_t wifi_config = {};
    if (ssid != NULL) {
        strncpy((char *)wifi_config.sta.ssid, ssid, sizeof(wifi_config.sta.ssid) - 1);
    }
    if (pass != NULL) {
        strncpy((char *)wifi_config.sta.password, pass, sizeof(wifi_config.sta.password) - 1);
    }
    wifi_config.sta.threshold.authmode = WIFI_AUTH_OPEN;


    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "Wi-Fi setup complete. Target SSID: '%s'", ssid ? ssid : "");
    return true;
}

bool mqtt_is_connected(void) {
    return s_mqtt_connected;
}

bool mqtt_publish_mock_data(int hr, int spo2, int16_t ax, int16_t ay, int16_t az, int battery) {
    if (!s_mqtt_connected || s_mqtt_client == NULL) {
        return false;
    }

    uint32_t timestamp = (uint32_t)(esp_timer_get_time() / 1000000ULL);

    // Build JSON object
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "device_id", "Health_Node_ESP32");
    cJSON_AddNumberToObject(root, "timestamp", timestamp);
    cJSON_AddNumberToObject(root, "heart_rate", hr);
    cJSON_AddNumberToObject(root, "spo2", spo2);
    
    cJSON *imu = cJSON_CreateObject();
    cJSON_AddNumberToObject(imu, "ax", ax);
    cJSON_AddNumberToObject(imu, "ay", ay);
    cJSON_AddNumberToObject(imu, "az", az);
    cJSON_AddItemToObject(root, "imu", imu);

    cJSON_AddNumberToObject(root, "battery", battery);

    char *json_str = cJSON_PrintUnformatted(root);
    if (json_str == NULL) {
        cJSON_Delete(root);
        return false;
    }

    int msg_id = esp_mqtt_client_publish(s_mqtt_client, "health/node/data", json_str, 0, 1, 0);
    ESP_LOGI(TAG, "[MQTT PUB] Topic: 'health/node/data' -> %s (msg_id=%d)", json_str, msg_id);

    free(json_str);
    cJSON_Delete(root);
    return (msg_id != -1);
}
