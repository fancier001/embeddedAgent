#ifndef MINIMAL_FIRMWARE_STATUS_LED_H
#define MINIMAL_FIRMWARE_STATUS_LED_H

#include <stdbool.h>
#include <stdint.h>

typedef enum
{
    STATUS_LED_OK = 0,
    STATUS_LED_INVALID_ARGUMENT = 1,
    STATUS_LED_NOT_INITIALIZED = 2,
    STATUS_LED_HAL_ERROR = 3
} status_led_result_t;

/** Initialize the status LED GPIO and drive it low. */
status_led_result_t status_led_init(uint32_t pin);

/** Set the status LED output after initialization. */
status_led_result_t status_led_set(bool enabled);

#endif
