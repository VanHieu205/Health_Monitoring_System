#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "app_config.h"
#include "mqtt_service.h"
#include <stdlib.h>
#include <stdio.h>

static const char *TAG = "Scheduler";

void sensor_acquisition_task(void *pvParameters) {
    while (1) {
        // Collect PPG and IMU (placeholder for physical sensors)
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

void ai_inference_task(void *pvParameters) {
    while (1) {
        // Run AI inference (placeholder)
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

void mqtt_transmission_task(void *pvParameters) {
    ESP_LOGI(TAG, "MQTT transmission task started (Mock Data Generator)");

    while (1) {
        // 1. Generate synthetic mock data
        int heart_rate = 70 + (rand() % 25);     // 70 - 94 bpm
        int spo2       = 96 + (rand() % 4);      // 96 - 99 %
        int16_t ax     = (rand() % 200) - 100;   // Slight acceleration jitter
        int16_t ay     = (rand() % 200) - 100;
        int16_t az     = 9800 + (rand() % 50);   // ~1G gravity vector
        int battery    = 90;                     // 90%

        // 2. Publish via MQTT if connected
        if (mqtt_is_connected()) {
            mqtt_publish_mock_data(heart_rate, spo2, ax, ay, az, battery);
        } else {
            ESP_LOGD(TAG, "Waiting for MQTT connection to Raspberry Pi...");
        }

        // Transmission interval configured in app_config.h (default 1000 ms)
        vTaskDelay(pdMS_TO_TICKS(MQTT_PUBLISH_INTERVAL_MS));
    }
}

void init_task_scheduler(void) {
    // 1. Initialize Wi-Fi and connect to MQTT broker
    ESP_LOGI(TAG, "Initializing Wi-Fi and MQTT Client...");
    init_wifi_and_mqtt(WIFI_SSID, WIFI_PASSWORD, MQTT_BROKER_URI);

    // 2. Spawn FreeRTOS tasks
    xTaskCreate(sensor_acquisition_task, "SensorTask", 2048, NULL, 5, NULL);
    xTaskCreate(ai_inference_task, "InferenceTask", 4096, NULL, 4, NULL);
    xTaskCreate(mqtt_transmission_task, "MQTTTask", 4096, NULL, 3, NULL);
}
