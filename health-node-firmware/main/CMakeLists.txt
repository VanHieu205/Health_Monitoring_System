idf_component_register(SRCS "main.cpp" "task_scheduler.cpp"
                    INCLUDE_DIRS "."
                    REQUIRES mqtt_service)
