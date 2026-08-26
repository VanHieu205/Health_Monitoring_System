package com.health.api.domain.device;

import java.util.Optional;

public interface DeviceRepository {
    Optional<Device> findById(String deviceId);
    Device save(Device device);
}
