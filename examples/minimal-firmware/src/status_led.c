#include "status_led.h"

#include "hal_gpio.h"

#define STATUS_LED_MAX_FAKE_PIN (31U)

static uint32_t status_led_pin;
static bool status_led_initialized;

status_led_result_t status_led_init(uint32_t pin)
{
    if (pin > STATUS_LED_MAX_FAKE_PIN)
    {
        return STATUS_LED_INVALID_ARGUMENT;
    }

    if (hal_gpio_configure_output(pin) != HAL_GPIO_OK)
    {
        return STATUS_LED_HAL_ERROR;
    }
    if (hal_gpio_write(pin, false) != HAL_GPIO_OK)
    {
        return STATUS_LED_HAL_ERROR;
    }

    status_led_pin = pin;
    status_led_initialized = true;
    return STATUS_LED_OK;
}

status_led_result_t status_led_set(bool enabled)
{
    if (!status_led_initialized)
    {
        return STATUS_LED_NOT_INITIALIZED;
    }
    if (hal_gpio_write(status_led_pin, enabled) != HAL_GPIO_OK)
    {
        return STATUS_LED_HAL_ERROR;
    }
    return STATUS_LED_OK;
}
