package com.health.api.infrastructure.persistence.postgres;

import com.health.api.domain.patient.Patient;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface PatientJpaRepository extends JpaRepository<Patient, String> {}
