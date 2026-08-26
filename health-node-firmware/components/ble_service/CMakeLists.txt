idf_component_register(SRCS "ble_gatt_server.cpp" "ble_packet_codec.cpp" "ble_connection_manager.cpp" "ble_security.cpp"
                       INCLUDE_DIRS "."
                       REQUIRES bt)
