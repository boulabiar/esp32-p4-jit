#pragma once

#include <stddef.h>

/**
 * @brief Initialize protocol buffers.
 *
 * @param rx_buffer_size Size of RX buffer (0 for default)
 * @param tx_buffer_size Size of TX buffer (0 for default)
 * @return 0 on success, -1 on failure
 */
int protocol_init(size_t rx_buffer_size, size_t tx_buffer_size);

/**
 * @brief Main protocol loop. Reads packets and dispatches commands.
 * Does not return. Must call protocol_init() first.
 */
void protocol_loop(void);
