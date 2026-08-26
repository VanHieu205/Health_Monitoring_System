package com.health.api.domain.alert;

import com.health.api.domain.vitalsign.VitalSignReading;

public class AlertRule {
    public static boolean evaluateFall(VitalSignReading reading) {
        return (reading.getEventFlag() & 0x01) != 0;
    }
}
