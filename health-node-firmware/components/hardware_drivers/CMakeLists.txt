idf_component_register(SRCS "max30102_driver/max30102.cpp"
                            "mpu6050_driver/mpu6050.cpp"
                            "mpu6050_driver/mpu6050_fifo.cpp"
                            "battery_monitor/battery_adc.cpp"
                            "power_management/deep_sleep_ctrl.cpp"
                       INCLUDE_DIRS "max30102_driver" "mpu6050_driver" "battery_monitor" "power_management"
                       REQUIRES driver esp_adc)
