idf_component_register(SRCS "main.cpp" "task_scheduler.cpp"
                    INCLUDE_DIRS "."
                    REQUIRES hardware_drivers signal_processing snn_inference ble_service ota_updater)
