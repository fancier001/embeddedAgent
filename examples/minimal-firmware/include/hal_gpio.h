#ifndef MINIMAL_FIRMWARE_HAL_GPIO_H
#define MINIMAL_FIRMWARE_HAL_GPIO_H

#include <stdbool.h>
#include <stdint.h>

typedef enum
{
    HAL_GPIO_OK = 0,
    HAL_GPIO_ERROR = 1
} hal_gpio_result_t;

hal_gpio_result_t hal_gpio_configure_output(uint32_t pin);
hal_gpio_result_t hal_gpio_write(uint32_t pin, bool high);

#endif
