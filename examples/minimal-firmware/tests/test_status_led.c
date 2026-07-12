#include <stdio.h>

#include "fake_hal_gpio.h"
#include "status_led.h"

#define CHECK(condition)                                                         \
    do                                                                           \
    {                                                                            \
        if (!(condition))                                                        \
        {                                                                        \
            (void)fprintf(stderr, "CHECK failed at %s:%d: %s\n",                \
                          __FILE__, __LINE__, #condition);                        \
            return 1;                                                            \
        }                                                                        \
    } while (0)

static int test_initialization_and_write(void)
{
    fake_hal_gpio_reset();
    CHECK(status_led_init(7U) == STATUS_LED_OK);
    CHECK(fake_hal_gpio_is_configured());
    CHECK(fake_hal_gpio_pin() == 7U);
    CHECK(fake_hal_gpio_configure_call_count() == 1U);
    CHECK(fake_hal_gpio_write_call_count() == 1U);
    CHECK(!fake_hal_gpio_last_requested_level());
    CHECK(!fake_hal_gpio_level());
    CHECK(status_led_set(true) == STATUS_LED_OK);
    CHECK(fake_hal_gpio_level());
    return 0;
}

static int test_invalid_pin(void)
{
    fake_hal_gpio_reset();
    CHECK(status_led_set(true) == STATUS_LED_NOT_INITIALIZED);
    CHECK(status_led_init(32U) == STATUS_LED_INVALID_ARGUMENT);
    CHECK(!fake_hal_gpio_is_configured());
    return 0;
}

static int test_configure_failure(void)
{
    fake_hal_gpio_reset();
    fake_hal_gpio_fail_next(FAKE_HAL_GPIO_CONFIGURE_OUTPUT);
    CHECK(status_led_init(3U) == STATUS_LED_HAL_ERROR);
    CHECK(fake_hal_gpio_configure_call_count() == 1U);
    CHECK(fake_hal_gpio_write_call_count() == 0U);
    CHECK(!fake_hal_gpio_is_configured());
    return 0;
}

static int test_initial_low_write_failure(void)
{
    fake_hal_gpio_reset();
    fake_hal_gpio_fail_next(FAKE_HAL_GPIO_WRITE);
    CHECK(status_led_init(3U) == STATUS_LED_HAL_ERROR);
    CHECK(fake_hal_gpio_is_configured());
    CHECK(fake_hal_gpio_write_call_count() == 1U);
    CHECK(!fake_hal_gpio_last_requested_level());
    CHECK(status_led_set(true) == STATUS_LED_NOT_INITIALIZED);
    return 0;
}

static int test_set_write_failure(void)
{
    fake_hal_gpio_reset();
    CHECK(status_led_init(5U) == STATUS_LED_OK);
    fake_hal_gpio_fail_next(FAKE_HAL_GPIO_WRITE);
    CHECK(status_led_set(true) == STATUS_LED_HAL_ERROR);
    CHECK(!fake_hal_gpio_level());
    CHECK(fake_hal_gpio_write_call_count() == 2U);
    CHECK(fake_hal_gpio_last_requested_level());
    return 0;
}

int main(void)
{
    int result = test_invalid_pin();
    if (result == 0)
    {
        result = test_configure_failure();
    }
    if (result == 0)
    {
        result = test_initial_low_write_failure();
    }
    if (result == 0)
    {
        result = test_initialization_and_write();
    }
    if (result == 0)
    {
        result = test_set_write_failure();
    }
    return result;
}
