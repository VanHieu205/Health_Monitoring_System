# ADR-001: Selection of Polyrepo Architecture with Shared Contracts

## Status
Accepted

## Context
The 3-tier health monitoring system spans C++ (ESP-IDF/FreeRTOS), Python (K3s/Edge AI), and Java (Spring Boot/TimescaleDB).

## Decision
Adopt a Polyrepo strategy with a centralized `health-shared-contracts` repository containing Protobuf, OpenAPI, and binary packet definitions.

## Consequences
- Independent build pipelines, versioning (SemVer), and isolated security per tier.
- Strict contract enforcement across tiers without mono-build overhead.
