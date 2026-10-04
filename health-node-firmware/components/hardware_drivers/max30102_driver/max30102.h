#ifndef MAX30102_H
#define MAX30102_H
#include <stdint.h>
#include "driver/i2c.h"
#include "driver/gpio.h"

#define MAX30102_I2C_ADDR         0x57
#define MAX30102_FIFO_SIZE        32
#define MAX30102_SAMPLE_BYTES     6  // 3 bytes per LED value
#define MAX30102_MAX_RETRIES      3

class MAX30102 {
public:
    MAX30102(i2c_port_t port, gpio_num_t int_pin);
    ~MAX30102();

    bool init();
    bool reset();
    bool set_mode(uint8_t mode);  // 0x02=RED, 0x03=RED+IR
    bool set_sample_rate(uint16_t rate_hz);
    bool set_led_current(uint8_t red_pa, uint8_t ir_pa);
    bool read_fifo_data(uint32_t *red, uint32_t *ir);
    bool read_raw_samples(uint32_t *red, uint32_t *ir);
    uint8_t get_interrupt_status();
    bool clear_interrupt();

private:
    i2c_port_t i2c_port;
    gpio_num_t interrupt_pin;
    uint8_t fifo_buffer[MAX30102_FIFO_SIZE * MAX30102_SAMPLE_BYTES];

    bool write_register(uint8_t reg, uint8_t value);
    bool read_register(uint8_t reg, uint8_t *value);
    bool read_bytes(uint8_t reg, uint8_t *data, size_t len);
};

#endif
