#ifndef MPU6050_H
#define MPU6050_H
#include <stdint.h>

class MPU6050 {
public:
    bool init();
    void read_accel_gyro(int16_t *ax, int16_t *ay, int16_t *az, int16_t *gx, int16_t *gy, int16_t *gz);
};
#endif
