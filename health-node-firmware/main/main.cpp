#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "app_config.h"

extern void init_task_scheduler(void);

extern "C" void app_main(void) {
    printf("[NODE] Starting 3-Tier Health Monitoring Node (ESP32-C3)...\n");
    init_task_scheduler();
}
