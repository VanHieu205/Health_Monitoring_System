#ifndef MAX30102_H
#define MAX30102_H
#include <stdint.h>

class MAX30102 {
public:
    bool init();
    bool read_raw_samples(uint32_t *red, uint32_t *ir);
};
#endif
