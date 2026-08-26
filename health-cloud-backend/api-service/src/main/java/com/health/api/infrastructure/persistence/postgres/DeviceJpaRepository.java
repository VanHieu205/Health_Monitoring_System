package com.health.api.infrastructure.persistence.postgres;

import com.health.api.domain.device.Device;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface DeviceJpaRepository extends JpaRepository<Device, String> {}
