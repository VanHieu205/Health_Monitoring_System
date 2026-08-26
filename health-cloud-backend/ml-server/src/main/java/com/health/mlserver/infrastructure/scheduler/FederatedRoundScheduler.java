package com.health.mlserver.infrastructure.scheduler;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class FederatedRoundScheduler {
    @Scheduled(cron = "0 0 3 * * ?")
    public void triggerNightlyRound() {}
}
