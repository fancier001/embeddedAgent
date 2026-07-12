#include "fake_hal_gpio.h"

#include "hal_gpio.h"

static bool configured;
static bool level;
static bool last_requested_level;
static bool failure_armed;
static fake_hal_gpio_operation_t failed_operation;
static uint32_t configured_pin;
static uint32_t configure_call_count;
static uint32_t write_call_count;

void fake_hal_gpio_reset(void)
{
    configured = false;
    level = false;
    last_requested_level = false;
    failure_armed = false;
    failed_operation = FAKE_HAL_GPIO_CONFIGURE_OUTPUT;
    configured_pin = 0U;
    configure_call_count = 0U;
    write_call_count = 0U;
}

void fake_hal_gpio_fail_next(fake_hal_gpio_operation_t operation)
{
    failure_armed = true;
    failed_operation = operation;
}

bool fake_hal_gpio_is_configured(void)
{
    return configured;
}

bool fake_hal_gpio_level(void)
{
    return level;
}

uint32_t fake_hal_gpio_pin(void)
{
    return configured_pin;
}

uint32_t fake_hal_gpio_configure_call_count(void)
{
    return configure_call_count;
}

uint32_t fake_hal_gpio_write_call_count(void)
{
    return write_call_count;
}

bool fake_hal_gpio_last_requested_level(void)
{
    return last_requested_level;
}

static bool consume_failure(fake_hal_gpio_operation_t operation)
{
    bool should_fail = failure_armed && (failed_operation == operation);
    if (should_fail)
    {
        failure_armed = false;
    }
    return should_fail;
}

hal_gpio_result_t hal_gpio_configure_output(uint32_t pin)
{
    configure_call_count++;
    if (consume_failure(FAKE_HAL_GPIO_CONFIGURE_OUTPUT))
    {
        return HAL_GPIO_ERROR;
    }
    configured = true;
    configured_pin = pin;
    return HAL_GPIO_OK;
}

hal_gpio_result_t hal_gpio_write(uint32_t pin, bool high)
{
    write_call_count++;
    last_requested_level = high;
    if (consume_failure(FAKE_HAL_GPIO_WRITE) || !configured ||
        (pin != configured_pin))
    {
        return HAL_GPIO_ERROR;
    }
    level = high;
    return HAL_GPIO_OK;
}
