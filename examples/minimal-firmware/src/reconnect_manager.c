#include "reconnect_manager.h"

#include <stddef.h>

#define RECONNECT_MAX_RETRIES (3U)

static const uint32_t retry_delays_ms[RECONNECT_MAX_RETRIES] =
{
    1000U,
    2000U,
    4000U
};

static void clear_action(reconnect_action_t *action)
{
    action->type = RECONNECT_ACTION_NONE;
    action->delay_ms = 0U;
}

void reconnect_manager_init(reconnect_manager_t *manager)
{
    if (manager != NULL)
    {
        manager->state = RECONNECT_STATE_CONNECTED;
        manager->retry_count = 0U;
    }
}

reconnect_result_t reconnect_manager_handle(reconnect_manager_t *manager,
                                            reconnect_event_t event,
                                            reconnect_action_t *action)
{
    if ((manager == NULL) || (action == NULL))
    {
        return RECONNECT_INVALID_ARGUMENT;
    }
    clear_action(action);

    if (event == RECONNECT_EVENT_USER_STOP)
    {
        if (manager->state == RECONNECT_STATE_STOPPED)
        {
            return RECONNECT_IGNORED;
        }
        if (manager->state == RECONNECT_STATE_WAITING)
        {
            action->type = RECONNECT_ACTION_CANCEL_RETRY;
        }
        manager->state = RECONNECT_STATE_STOPPED;
        return RECONNECT_HANDLED;
    }

    switch (manager->state)
    {
        case RECONNECT_STATE_CONNECTED:
            if (event == RECONNECT_EVENT_LINK_DOWN)
            {
                manager->retry_count = 0U;
                manager->state = RECONNECT_STATE_WAITING;
                action->type = RECONNECT_ACTION_SCHEDULE_RETRY;
                action->delay_ms = retry_delays_ms[0];
                return RECONNECT_HANDLED;
            }
            break;

        case RECONNECT_STATE_WAITING:
            if (event == RECONNECT_EVENT_TIMER_EXPIRED)
            {
                manager->retry_count++;
                manager->state = RECONNECT_STATE_CONNECTING;
                action->type = RECONNECT_ACTION_REQUEST_CONNECT;
                return RECONNECT_HANDLED;
            }
            break;

        case RECONNECT_STATE_CONNECTING:
            if (event == RECONNECT_EVENT_CONNECT_SUCCEEDED)
            {
                manager->retry_count = 0U;
                manager->state = RECONNECT_STATE_CONNECTED;
                return RECONNECT_HANDLED;
            }
            if (event == RECONNECT_EVENT_CONNECT_FAILED)
            {
                if (manager->retry_count < RECONNECT_MAX_RETRIES)
                {
                    manager->state = RECONNECT_STATE_WAITING;
                    action->type = RECONNECT_ACTION_SCHEDULE_RETRY;
                    action->delay_ms = retry_delays_ms[manager->retry_count];
                }
                else
                {
                    manager->state = RECONNECT_STATE_EXHAUSTED;
                    action->type = RECONNECT_ACTION_REPORT_EXHAUSTED;
                }
                return RECONNECT_HANDLED;
            }
            break;

        case RECONNECT_STATE_EXHAUSTED:
        case RECONNECT_STATE_STOPPED:
        default:
            break;
    }
    return RECONNECT_IGNORED;
}
