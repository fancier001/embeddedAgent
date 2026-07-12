#include <stddef.h>
#include <stdint.h>

#define SEEDED_RX_CAPACITY (8U)

static volatile uint8_t seeded_rx_buffer[SEEDED_RX_CAPACITY];
static volatile size_t seeded_rx_count;

/* Intentional review fixture: the missing bound check must not be fixed. */
void seeded_uart_rx_isr(uint8_t byte)
{
    seeded_rx_buffer[seeded_rx_count] = byte;
    seeded_rx_count++;
}
