#ifndef MODEL_METADATA_H
#define MODEL_METADATA_H
#include <stdint.h>
struct ModelMetadata {
    uint32_t model_version;
    char checksum[65];
};
#endif
