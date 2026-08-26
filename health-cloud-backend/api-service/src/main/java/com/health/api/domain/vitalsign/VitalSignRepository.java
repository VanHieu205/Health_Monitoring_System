package com.health.api.domain.vitalsign;

import java.util.List;

public interface VitalSignRepository {
    void save(VitalSignReading reading);
    List<VitalSignReading> findByDeviceAndRange(String deviceId, long startTs, long endTs);
}
