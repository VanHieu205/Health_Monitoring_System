#include "max30102.h"
#include "max30102_registers.h"
#include "esp_log.h"

static const char *TAG = "MAX30102";

MAX30102::MAX30102(i2c_port_t port, gpio_num_t int_pin)
    : i2c_port(port), interrupt_pin(int_pin) {}

MAX30102::~MAX30102() {}

bool MAX30102::init() {
    if (!reset()) {
        ESP_LOGE(TAG, "Reset failed");
        return false;
    }

    if (!set_mode(0x03)) {  // RED + IR mode
        ESP_LOGE(TAG, "Set mode failed");
        return false;
    }

    if (!set_sample_rate(100)) {  // 100 Hz
        ESP_LOGE(TAG, "Set sample rate failed");
        return false;
    }

    if (!set_led_current(0x1F, 0x1F)) {  // Max current for both LEDs
        ESP_LOGE(TAG, "Set LED current failed");
        return false;
    }

    // Clear interrupt flags
    clear_interrupt();

    ESP_LOGI(TAG, "MAX30102 initialized successfully");
    return true;
}

bool MAX30102::reset() {
    return write_register(MAX30102_MODE_CONFIG, 0x40);  // RESET bit
}

bool MAX30102::set_mode(uint8_t mode) {
    return write_register(MAX30102_MODE_CONFIG, mode);
}

bool MAX30102::set_sample_rate(uint16_t rate_hz) {
    uint8_t config = 0;

    if (rate_hz <= 50)
        config = 0x00;  // 50 Hz
    else if (rate_hz <= 100)
        config = 0x04;  // 100 Hz
    else if (rate_hz <= 200)
        config = 0x08;  // 200 Hz
    else
        config = 0x0C;  // 400 Hz

    return write_register(MAX30102_SPO2_CONFIG, config);
}

bool MAX30102::set_led_current(uint8_t red_pa, uint8_t ir_pa) {
    return write_register(MAX30102_LED1_PA, red_pa) &&
           write_register(MAX30102_LED2_PA, ir_pa);
}

bool MAX30102::read_fifo_data(uint32_t *red, uint32_t *ir) {
    uint8_t fifo_data[6];

    if (!read_bytes(MAX30102_FIFO_DATA, fifo_data, 6)) {
        ESP_LOGE(TAG, "FIFO read failed");
        return false;
    }

    // Extract 24-bit values from FIFO
    *red = ((uint32_t)fifo_data[0] << 16) | ((uint32_t)fifo_data[1] << 8) | fifo_data[2];
    *ir = ((uint32_t)fifo_data[3] << 16) | ((uint32_t)fifo_data[4] << 8) | fifo_data[5];

    *red &= 0x3FFFF;  // Mask to 18 bits
    *ir &= 0x3FFFF;

    return true;
}

bool MAX30102::read_raw_samples(uint32_t *red, uint32_t *ir) {
    return read_fifo_data(red, ir);
}

uint8_t MAX30102::get_interrupt_status() {
    uint8_t status;
    read_register(MAX30102_INT_STATUS_1, &status);
    return status;
}

bool MAX30102::clear_interrupt() {
    uint8_t status;
    return read_register(MAX30102_INT_STATUS_1, &status);  // Reading clears interrupt
}

bool MAX30102::write_register(uint8_t reg, uint8_t value) {
    for (int retry = 0; retry < MAX30102_MAX_RETRIES; retry++) {
        i2c_cmd_handle_t cmd = i2c_cmd_link_create();
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (MAX30102_I2C_ADDR << 1) | I2C_MASTER_WRITE, true);
        i2c_master_write_byte(cmd, reg, true);
        i2c_master_write_byte(cmd, value, true);
        i2c_master_stop(cmd);

        esp_err_t ret = i2c_master_cmd_begin(i2c_port, cmd, pdMS_TO_TICKS(100));
        i2c_cmd_link_delete(cmd);

        if (ret == ESP_OK)
            return true;
    }

    ESP_LOGE(TAG, "Write register 0x%02X failed", reg);
    return false;
}

bool MAX30102::read_register(uint8_t reg, uint8_t *value) {
    for (int retry = 0; retry < MAX30102_MAX_RETRIES; retry++) {
        i2c_cmd_handle_t cmd = i2c_cmd_link_create();
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (MAX30102_I2C_ADDR << 1) | I2C_MASTER_WRITE, true);
        i2c_master_write_byte(cmd, reg, true);
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (MAX30102_I2C_ADDR << 1) | I2C_MASTER_READ, true);
        i2c_master_read_byte(cmd, value, I2C_MASTER_NACK);
        i2c_master_stop(cmd);

        esp_err_t ret = i2c_master_cmd_begin(i2c_port, cmd, pdMS_TO_TICKS(100));
        i2c_cmd_link_delete(cmd);

        if (ret == ESP_OK)
            return true;
    }

    ESP_LOGE(TAG, "Read register 0x%02X failed", reg);
    return false;
}

bool MAX30102::read_bytes(uint8_t reg, uint8_t *data, size_t len) {
    for (int retry = 0; retry < MAX30102_MAX_RETRIES; retry++) {
        i2c_cmd_handle_t cmd = i2c_cmd_link_create();
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (MAX30102_I2C_ADDR << 1) | I2C_MASTER_WRITE, true);
        i2c_master_write_byte(cmd, reg, true);
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (MAX30102_I2C_ADDR << 1) | I2C_MASTER_READ, true);

        for (size_t i = 0; i < len; i++) {
            i2c_master_read_byte(cmd, &data[i], (i < len - 1) ? I2C_MASTER_ACK : I2C_MASTER_NACK);
        }

        i2c_master_stop(cmd);

        esp_err_t ret = i2c_master_cmd_begin(i2c_port, cmd, pdMS_TO_TICKS(100));
        i2c_cmd_link_delete(cmd);

        if (ret == ESP_OK)
            return true;
    }

    ESP_LOGE(TAG, "Read bytes from 0x%02X failed", reg);
    return false;
}
