#ifndef MINIMAL_FIRMWARE_FAKE_HAL_GPIO_H
#define MINIMAL_FIRMWARE_FAKE_HAL_GPIO_H

#include <stdbool.h>
#include <stdint.h>

typedef enum
{
    FAKE_HAL_GPIO_CONFIGURE_OUTPUT,
    FAKE_HAL_GPIO_WRITE
} fake_hal_gpio_operation_t;

void fake_hal_gpio_reset(void);
void fake_hal_gpio_fail_next(fake_hal_gpio_operation_t operation);
bool fake_hal_gpio_is_configured(void);
bool fake_hal_gpio_level(void);
uint32_t fake_hal_gpio_pin(void);
uint32_t fake_hal_gpio_configure_call_count(void);
uint32_t fake_hal_gpio_write_call_count(void);
bool fake_hal_gpio_last_requested_level(void);

#endif
