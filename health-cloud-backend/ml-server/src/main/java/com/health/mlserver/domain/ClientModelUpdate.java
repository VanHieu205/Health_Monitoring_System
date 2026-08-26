package com.health.mlserver.domain;

public class ClientModelUpdate {
    private String clientId;
    private byte[] modelDiff;
    private int sampleCount;
}
