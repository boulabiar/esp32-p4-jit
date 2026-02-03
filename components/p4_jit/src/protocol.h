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
 * @brief Get the configured max payload size.
 * @return Max payload size in bytes, or 0 if not initialized
 */
size_t protocol_get_max_payload_size(void);

/**
 * @brief Main protocol loop. Reads packets and dispatches commands.
 * Does not return. Must call protocol_init() first.
 */
void protocol_loop(void);
