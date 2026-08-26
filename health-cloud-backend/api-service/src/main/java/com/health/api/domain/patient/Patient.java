package com.health.api.domain.patient;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "patients")
public class Patient {
    @Id
    private String id;
    private String name;
    private int age;
}
