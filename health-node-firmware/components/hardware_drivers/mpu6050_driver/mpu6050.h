#ifndef MPU6050_H
#define MPU6050_H
#include <stdint.h>
#include "driver/i2c.h"

#define MPU6050_I2C_ADDR          0x68
#define MPU6050_PWR_MGMT_1        0x6B
#define MPU6050_GYRO_CONFIG       0x1B
#define MPU6050_ACCEL_CONFIG      0x1C
#define MPU6050_SMPLRT_DIV        0x19
#define MPU6050_ACCEL_DATA        0x3B
#define MPU6050_GYRO_DATA         0x43
#define MPU6050_MAX_RETRIES       3

class MPU6050 {
public:
    MPU6050(i2c_port_t port);
    ~MPU6050();

    bool init();
    bool reset();
    bool set_sample_rate(uint8_t rate_div);
    bool set_gyro_config(uint8_t range);    // 0=±250, 1=±500, 2=±1000, 3=±2000
    bool set_accel_config(uint8_t range);   // 0=±2g, 1=±4g, 2=±8g, 3=±16g
    bool read_accel_gyro(int16_t *ax, int16_t *ay, int16_t *az,
                         int16_t *gx, int16_t *gy, int16_t *gz);

    float get_accel_scale() const;
    float get_gyro_scale() const;

private:
    i2c_port_t i2c_port;
    uint8_t accel_scale;
    uint8_t gyro_scale;

    bool write_register(uint8_t reg, uint8_t value);
    bool read_register(uint8_t reg, uint8_t *value);
    bool read_bytes(uint8_t reg, uint8_t *data, size_t len);
};

#endif
