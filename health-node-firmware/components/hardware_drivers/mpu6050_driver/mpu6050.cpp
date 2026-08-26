#include "mpu6050.h"

bool MPU6050::init() { return true; }
void MPU6050::read_accel_gyro(int16_t *ax, int16_t *ay, int16_t *az, int16_t *gx, int16_t *gy, int16_t *gz) {
    *ax = 0; *ay = 0; *az = 16384;
    *gx = 0; *gy = 0; *gz = 0;
}
