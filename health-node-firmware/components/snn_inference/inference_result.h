#ifndef INFERENCE_RESULT_H
#define INFERENCE_RESULT_H
#include <stdint.h>
struct SNNInferenceResult {
    uint8_t classification_label; // 0: Normal, 1: Fall, 2: Anomaly
    float confidence;
    uint32_t latency_us;
};
#endif
