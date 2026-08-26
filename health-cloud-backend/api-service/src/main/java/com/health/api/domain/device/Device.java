package com.health.api.domain.device;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "devices")
public class Device {
    @Id
    private String deviceId;
    private String patientId;
    private String firmwareVersion;
    private DeviceStatus status;
}
