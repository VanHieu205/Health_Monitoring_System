package com.health.api.domain.alert;

import java.time.Instant;

public class HealthAlert {
    private String alertId;
    private String deviceId;
    private String alertType;
    private Instant createdAt;
}
