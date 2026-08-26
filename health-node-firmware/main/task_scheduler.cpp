#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdio.h>

void sensor_acquisition_task(void *pvParameters) {
    while (1) {
        // Collect PPG and IMU
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}

void ai_inference_task(void *pvParameters) {
    while (1) {
        // Run SNN inference (<5ms)
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

void ble_transmission_task(void *pvParameters) {
    while (1) {
        // Transmit 18-byte packed struct
        vTaskDelay(pdMS_TO_TICKS(200));
    }
}

void init_task_scheduler(void) {
    xTaskCreate(sensor_acquisition_task, "SensorTask", 2048, NULL, 5, NULL);
    xTaskCreate(ai_inference_task, "InferenceTask", 4096, NULL, 4, NULL);
    xTaskCreate(ble_transmission_task, "BLETask", 3072, NULL, 3, NULL);
}
