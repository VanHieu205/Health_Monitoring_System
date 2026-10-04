#include "mpu6050.h"
#include "esp_log.h"

static const char *TAG = "MPU6050";

// Accel scale in g per LSB (for 16-bit values)
static const float accel_scales[] = {0.00006103f, 0.0001220703f, 0.000244140625f, 0.00048828125f};
// Gyro scale in deg/s per LSB (for 16-bit values)
static const float gyro_scales[] = {0.00763359375f, 0.0152671875f, 0.030534375f, 0.06106875f};

MPU6050::MPU6050(i2c_port_t port)
    : i2c_port(port), accel_scale(0), gyro_scale(0) {}

MPU6050::~MPU6050() {}

bool MPU6050::init() {
    if (!reset()) {
        ESP_LOGE(TAG, "Reset failed");
        return false;
    }

    // Enable gyro + accel, disable sleep
    if (!write_register(MPU6050_PWR_MGMT_1, 0x00)) {
        ESP_LOGE(TAG, "Power management setup failed");
        return false;
    }

    // Set sample rate to 50 Hz (divider = 15)
    if (!set_sample_rate(15)) {
        ESP_LOGE(TAG, "Set sample rate failed");
        return false;
    }

    // Set gyro range to ±1000 deg/s
    if (!set_gyro_config(2)) {
        ESP_LOGE(TAG, "Set gyro config failed");
        return false;
    }

    // Set accel range to ±8g
    if (!set_accel_config(2)) {
        ESP_LOGE(TAG, "Set accel config failed");
        return false;
    }

    ESP_LOGI(TAG, "MPU6050 initialized successfully");
    return true;
}

bool MPU6050::reset() {
    // Write 0x80 to reset all registers
    return write_register(MPU6050_PWR_MGMT_1, 0x80);
}

bool MPU6050::set_sample_rate(uint8_t rate_div) {
    return write_register(MPU6050_SMPLRT_DIV, rate_div);
}

bool MPU6050::set_gyro_config(uint8_t range) {
    if (range > 3) return false;

    gyro_scale = range;
    uint8_t config = (range << 3);  // Bits 4:3
    return write_register(MPU6050_GYRO_CONFIG, config);
}

bool MPU6050::set_accel_config(uint8_t range) {
    if (range > 3) return false;

    accel_scale = range;
    uint8_t config = (range << 3);  // Bits 4:3
    return write_register(MPU6050_ACCEL_CONFIG, config);
}

bool MPU6050::read_accel_gyro(int16_t *ax, int16_t *ay, int16_t *az,
                              int16_t *gx, int16_t *gy, int16_t *gz) {
    uint8_t data[14];

    // Read 14 bytes starting from ACCEL_DATA (3B = accel, 40 = temp, 43 = gyro)
    if (!read_bytes(MPU6050_ACCEL_DATA, data, 14)) {
        ESP_LOGE(TAG, "Read accel/gyro data failed");
        return false;
    }

    // Extract 16-bit accel values (big-endian)
    *ax = (int16_t)((data[0] << 8) | data[1]);
    *ay = (int16_t)((data[2] << 8) | data[3]);
    *az = (int16_t)((data[4] << 8) | data[5]);

    // Extract 16-bit gyro values (skip temp at bytes 6-7)
    *gx = (int16_t)((data[8] << 8) | data[9]);
    *gy = (int16_t)((data[10] << 8) | data[11]);
    *gz = (int16_t)((data[12] << 8) | data[13]);

    return true;
}

float MPU6050::get_accel_scale() const {
    return accel_scales[accel_scale];
}

float MPU6050::get_gyro_scale() const {
    return gyro_scales[gyro_scale];
}

bool MPU6050::write_register(uint8_t reg, uint8_t value) {
    for (int retry = 0; retry < MPU6050_MAX_RETRIES; retry++) {
        i2c_cmd_handle_t cmd = i2c_cmd_link_create();
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (MPU6050_I2C_ADDR << 1) | I2C_MASTER_WRITE, true);
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

bool MPU6050::read_register(uint8_t reg, uint8_t *value) {
    for (int retry = 0; retry < MPU6050_MAX_RETRIES; retry++) {
        i2c_cmd_handle_t cmd = i2c_cmd_link_create();
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (MPU6050_I2C_ADDR << 1) | I2C_MASTER_WRITE, true);
        i2c_master_write_byte(cmd, reg, true);
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (MPU6050_I2C_ADDR << 1) | I2C_MASTER_READ, true);
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

bool MPU6050::read_bytes(uint8_t reg, uint8_t *data, size_t len) {
    for (int retry = 0; retry < MPU6050_MAX_RETRIES; retry++) {
        i2c_cmd_handle_t cmd = i2c_cmd_link_create();
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (MPU6050_I2C_ADDR << 1) | I2C_MASTER_WRITE, true);
        i2c_master_write_byte(cmd, reg, true);
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (MPU6050_I2C_ADDR << 1) | I2C_MASTER_READ, true);

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
