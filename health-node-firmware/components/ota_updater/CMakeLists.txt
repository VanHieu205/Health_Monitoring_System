idf_component_register(SRCS "ota_ble_receiver.cpp" "ota_flash_writer.cpp" "ota_rollback_guard.cpp"
                       INCLUDE_DIRS "."
                       REQUIRES app_update esp_partition)
