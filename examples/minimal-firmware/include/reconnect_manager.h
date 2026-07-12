#ifndef MINIMAL_FIRMWARE_RECONNECT_MANAGER_H
#define MINIMAL_FIRMWARE_RECONNECT_MANAGER_H

#include <stdint.h>

typedef enum
{
    RECONNECT_STATE_CONNECTED,
    RECONNECT_STATE_WAITING,
    RECONNECT_STATE_CONNECTING,
    RECONNECT_STATE_EXHAUSTED,
    RECONNECT_STATE_STOPPED
} reconnect_state_t;

typedef enum
{
    RECONNECT_EVENT_LINK_DOWN,
    RECONNECT_EVENT_TIMER_EXPIRED,
    RECONNECT_EVENT_CONNECT_SUCCEEDED,
    RECONNECT_EVENT_CONNECT_FAILED,
    RECONNECT_EVENT_USER_STOP
} reconnect_event_t;

typedef enum
{
    RECONNECT_ACTION_NONE,
    RECONNECT_ACTION_SCHEDULE_RETRY,
    RECONNECT_ACTION_REQUEST_CONNECT,
    RECONNECT_ACTION_CANCEL_RETRY,
    RECONNECT_ACTION_REPORT_EXHAUSTED
} reconnect_action_type_t;

typedef enum
{
    RECONNECT_HANDLED,
    RECONNECT_IGNORED,
    RECONNECT_INVALID_ARGUMENT
} reconnect_result_t;

typedef struct
{
    reconnect_action_type_t type;
    uint32_t delay_ms;
} reconnect_action_t;

typedef struct
{
    reconnect_state_t state;
    uint8_t retry_count;
} reconnect_manager_t;

void reconnect_manager_init(reconnect_manager_t *manager);
reconnect_result_t reconnect_manager_handle(reconnect_manager_t *manager,
                                            reconnect_event_t event,
                                            reconnect_action_t *action);

#endif
