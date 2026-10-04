#include <stdint.h>
#include "driver/adc.h"
#include "esp_log.h"

static const char *TAG = "BatteryMonitor";

// Battery voltage thresholds (mV)
#define BATTERY_MAX_MV          4200
#define BATTERY_MIN_MV          3000
#define BATTERY_CRITICAL_MV     2800

// Calibration for ADC (depends on voltage divider)
#define ADC_VREF_MV             3300
#define ADC_CHANNEL             ADC1_CHANNEL_0
#define ADC_RESOLUTION          4095
#define VOLTAGE_DIVIDER_RATIO   2.0  // Example: 100k + 100k divider

static uint32_t battery_voltage_mv = 4200;

void init_battery_monitor() {
    // Configure ADC1
    adc1_config_width(ADC_WIDTH_BIT_12);
    adc1_config_channel_atten(ADC_CHANNEL, ADC_ATTEN_DB_11);

    ESP_LOGI(TAG, "Battery monitor initialized");
}

uint32_t read_battery_voltage_mv() {
    // Read raw ADC value
    uint32_t adc_raw = adc1_get_raw(ADC_CHANNEL);

    // Convert to voltage (mV)
    uint32_t vref_mv = ADC_VREF_MV;
    uint32_t voltage_mv = (adc_raw * vref_mv) / ADC_RESOLUTION;

    // Apply voltage divider correction
    voltage_mv = (uint32_t)(voltage_mv * VOLTAGE_DIVIDER_RATIO);

    battery_voltage_mv = voltage_mv;
    return voltage_mv;
}

uint8_t read_battery_percentage() {
    uint32_t voltage_mv = read_battery_voltage_mv();

    // Linear interpolation between min and max
    if (voltage_mv >= BATTERY_MAX_MV)
        return 100;

    if (voltage_mv <= BATTERY_MIN_MV)
        return 0;

    // Percent = (voltage - min) / (max - min) * 100
    uint8_t percent = ((voltage_mv - BATTERY_MIN_MV) * 100) /
                      (BATTERY_MAX_MV - BATTERY_MIN_MV);

    return percent > 100 ? 100 : percent;
}

bool is_battery_critical() {
    return battery_voltage_mv < BATTERY_CRITICAL_MV;
}

bool is_battery_low() {
    return battery_voltage_mv < BATTERY_MIN_MV;
}
