package com.health.api.domain.vitalsign;

import java.time.Instant;

public class VitalSignReading {
    private String deviceId;
    private Instant timestamp;
    private double heartRate;
    private double spo2;
    private double accelMagnitude;
    private int eventFlag;
}
