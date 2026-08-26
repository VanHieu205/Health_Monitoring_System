package com.health.mlserver.application;

import com.health.mlserver.domain.ClientModelUpdate;
import com.health.mlserver.domain.GlobalModel;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
public class FedAvgAggregationUseCase {
    public GlobalModel aggregate(List<ClientModelUpdate> clientUpdates) {
        // FedAvg: w_{t+1} = \sum (n_k / n) * w_{t+1}^k
        return new GlobalModel();
    }
}
