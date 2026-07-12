#include <stdbool.h>
#include <stdio.h>

#include "reconnect_manager.h"

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

typedef struct
{
    bool armed;
    uint32_t delay_ms;
    uint32_t schedule_count;
    uint32_t cancel_count;
} fake_clock_t;

typedef struct
{
    uint32_t request_count;
} fake_network_t;

static void apply_action(const reconnect_action_t *action,
                         fake_clock_t *clock,
                         fake_network_t *network)
{
    if (action->type == RECONNECT_ACTION_SCHEDULE_RETRY)
    {
        clock->armed = true;
        clock->delay_ms = action->delay_ms;
        clock->schedule_count++;
    }
    else if (action->type == RECONNECT_ACTION_REQUEST_CONNECT)
    {
        clock->armed = false;
        network->request_count++;
    }
    else if (action->type == RECONNECT_ACTION_CANCEL_RETRY)
    {
        clock->armed = false;
        clock->cancel_count++;
    }
}

static int handle(reconnect_manager_t *manager,
                  reconnect_event_t event,
                  fake_clock_t *clock,
                  fake_network_t *network,
                  reconnect_action_t *action)
{
    CHECK(reconnect_manager_handle(manager, event, action) == RECONNECT_HANDLED);
    apply_action(action, clock, network);
    return 0;
}

static int test_backoff_and_exhaustion(void)
{
    reconnect_manager_t manager;
    reconnect_action_t action;
    fake_clock_t clock = {false, 0U, 0U, 0U};
    fake_network_t network = {0U};
    reconnect_manager_init(&manager);

    CHECK(handle(&manager, RECONNECT_EVENT_LINK_DOWN, &clock, &network, &action) == 0);
    CHECK(clock.delay_ms == 1000U);
    CHECK(handle(&manager, RECONNECT_EVENT_TIMER_EXPIRED, &clock, &network, &action) == 0);
    CHECK(handle(&manager, RECONNECT_EVENT_CONNECT_FAILED, &clock, &network, &action) == 0);
    CHECK(clock.delay_ms == 2000U);
    CHECK(handle(&manager, RECONNECT_EVENT_TIMER_EXPIRED, &clock, &network, &action) == 0);
    CHECK(handle(&manager, RECONNECT_EVENT_CONNECT_FAILED, &clock, &network, &action) == 0);
    CHECK(clock.delay_ms == 4000U);
    CHECK(handle(&manager, RECONNECT_EVENT_TIMER_EXPIRED, &clock, &network, &action) == 0);
    CHECK(handle(&manager, RECONNECT_EVENT_CONNECT_FAILED, &clock, &network, &action) == 0);
    CHECK(action.type == RECONNECT_ACTION_REPORT_EXHAUSTED);
    CHECK(manager.state == RECONNECT_STATE_EXHAUSTED);
    CHECK(manager.retry_count == 3U);
    CHECK(clock.schedule_count == 3U);
    CHECK(network.request_count == 3U);
    return 0;
}

static int test_duplicate_and_out_of_order_events(void)
{
    reconnect_manager_t manager;
    reconnect_action_t action;
    fake_clock_t clock = {false, 0U, 0U, 0U};
    fake_network_t network = {0U};
    reconnect_manager_init(&manager);

    CHECK(reconnect_manager_handle(&manager, RECONNECT_EVENT_TIMER_EXPIRED, &action) == RECONNECT_IGNORED);
    CHECK(handle(&manager, RECONNECT_EVENT_LINK_DOWN, &clock, &network, &action) == 0);
    CHECK(reconnect_manager_handle(&manager, RECONNECT_EVENT_LINK_DOWN, &action) == RECONNECT_IGNORED);
    CHECK(action.type == RECONNECT_ACTION_NONE);
    CHECK(clock.schedule_count == 1U);
    CHECK(handle(&manager, RECONNECT_EVENT_TIMER_EXPIRED, &clock, &network, &action) == 0);
    CHECK(handle(&manager, RECONNECT_EVENT_CONNECT_SUCCEEDED, &clock, &network, &action) == 0);
    CHECK(manager.state == RECONNECT_STATE_CONNECTED);
    CHECK(manager.retry_count == 0U);
    return 0;
}

static int test_user_stop_prevents_reconnect(void)
{
    reconnect_manager_t manager;
    reconnect_action_t action;
    fake_clock_t clock = {false, 0U, 0U, 0U};
    fake_network_t network = {0U};
    reconnect_manager_init(&manager);

    CHECK(handle(&manager, RECONNECT_EVENT_LINK_DOWN, &clock, &network, &action) == 0);
    CHECK(handle(&manager, RECONNECT_EVENT_USER_STOP, &clock, &network, &action) == 0);
    CHECK(action.type == RECONNECT_ACTION_CANCEL_RETRY);
    CHECK(clock.cancel_count == 1U);
    CHECK(reconnect_manager_handle(&manager, RECONNECT_EVENT_LINK_DOWN, &action) == RECONNECT_IGNORED);
    CHECK(reconnect_manager_handle(&manager, RECONNECT_EVENT_TIMER_EXPIRED, &action) == RECONNECT_IGNORED);
    CHECK(network.request_count == 0U);
    return 0;
}

static int test_invalid_arguments(void)
{
    reconnect_manager_t manager;
    reconnect_action_t action;
    reconnect_manager_init(&manager);
    CHECK(reconnect_manager_handle(NULL, RECONNECT_EVENT_LINK_DOWN, &action) == RECONNECT_INVALID_ARGUMENT);
    CHECK(reconnect_manager_handle(&manager, RECONNECT_EVENT_LINK_DOWN, NULL) == RECONNECT_INVALID_ARGUMENT);
    return 0;
}

int main(void)
{
    int result = test_backoff_and_exhaustion();
    if (result == 0)
    {
        result = test_duplicate_and_out_of_order_events();
    }
    if (result == 0)
    {
        result = test_user_stop_prevents_reconnect();
    }
    if (result == 0)
    {
        result = test_invalid_arguments();
    }
    return result;
}
