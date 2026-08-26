idf_component_register(SRCS "ppg_pipeline/bandpass_filter.cpp"
                            "ppg_pipeline/spo2_algorithm.cpp"
                            "ppg_pipeline/peak_detector.cpp"
                            "imu_pipeline/kalman_filter.cpp"
                            "imu_pipeline/feature_extractor.cpp"
                            "imu_pipeline/fall_heuristic.cpp"
                            "imu_pipeline/data_fusion.cpp"
                       INCLUDE_DIRS "ppg_pipeline" "imu_pipeline")
