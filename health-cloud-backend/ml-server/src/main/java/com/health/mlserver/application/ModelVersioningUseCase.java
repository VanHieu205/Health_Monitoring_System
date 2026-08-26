package com.health.mlserver.application;

import org.springframework.stereotype.Service;

@Service
public class ModelVersioningUseCase {
    public void registerNewModelVersion(String version, byte[] weights) {}
}
