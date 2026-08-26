#include "max30102.h"
#include "max30102_registers.h"

bool MAX30102::init() {
    return true;
}

bool MAX30102::read_raw_samples(uint32_t *red, uint32_t *ir) {
    *red = 50000;
    *ir = 52000;
    return true;
}
