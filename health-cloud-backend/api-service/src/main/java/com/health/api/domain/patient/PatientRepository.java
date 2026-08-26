package com.health.api.domain.patient;

import java.util.Optional;

public interface PatientRepository {
    Optional<Patient> findById(String id);
}
