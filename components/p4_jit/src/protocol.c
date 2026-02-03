#include "protocol.h"
#include "usb_transport.h"
#include "commands.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include <string.h>
#include <stdlib.h>

static const char *TAG = "protocol";

#define MAGIC_BYTE_1 0xA5
#define MAGIC_BYTE_2 0x5A

#pragma pack(push, 1)
typedef struct {
    uint8_t magic[2];
    uint8_t cmd_id;
    uint8_t flags;
    uint32_t payload_len;
} packet_header_t;
#pragma pack(pop)

// Default max payload size (1MB + overhead)
#ifdef CONFIG_P4_JIT_PAYLOAD_BUFFER_SIZE
#define DEFAULT_BUFFER_SIZE (CONFIG_P4_JIT_PAYLOAD_BUFFER_SIZE + 1024)
#else
#define DEFAULT_BUFFER_SIZE (1024 * 1024 + 1024)
#endif

static uint8_t *rx_buffer = NULL;
static uint8_t *tx_buffer = NULL;
static size_t max_payload_size = 0;

static uint16_t calculate_checksum(const uint8_t *data, size_t len) {
    uint16_t sum = 0;
    for (size_t i = 0; i < len; i++) {
        sum += data[i];
    }
    return sum;
}

void send_response(uint8_t cmd_id, uint8_t flags, uint8_t *payload, uint32_t len) {
    packet_header_t header;
    header.magic[0] = MAGIC_BYTE_1;
    header.magic[1] = MAGIC_BYTE_2;
    header.cmd_id = cmd_id;
    header.flags = flags;
    header.payload_len = len;

    // Calculate checksum (Header + Payload)
    uint16_t checksum = 0;
    checksum += calculate_checksum((uint8_t*)&header, sizeof(header));
    if (payload && len > 0) {
        checksum += calculate_checksum(payload, len);
    }

    usb_write_bytes((uint8_t*)&header, sizeof(header));
    if (payload && len > 0) {
        usb_write_bytes(payload, len);
    }
    usb_write_bytes((uint8_t*)&checksum, 2);
}

int protocol_init(size_t rx_buffer_size, size_t tx_buffer_size) {
    // Use provided sizes or defaults
    size_t rx_size = (rx_buffer_size > 0) ? rx_buffer_size : DEFAULT_BUFFER_SIZE;
    size_t tx_size = (tx_buffer_size > 0) ? tx_buffer_size : DEFAULT_BUFFER_SIZE;

    // Store max payload size (smaller of the two buffers minus header overhead)
    max_payload_size = (rx_size < tx_size) ? rx_size : tx_size;

    ESP_LOGI(TAG, "Allocating protocol buffers: RX=%u, TX=%u bytes", rx_size, tx_size);

    // Try SPIRAM first (with 8-bit access), fall back to internal RAM
    rx_buffer = heap_caps_malloc(rx_size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!rx_buffer) {
        ESP_LOGW(TAG, "SPIRAM allocation failed for RX, trying internal RAM");
        rx_buffer = heap_caps_malloc(rx_size, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    }

    tx_buffer = heap_caps_malloc(tx_size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!tx_buffer) {
        ESP_LOGW(TAG, "SPIRAM allocation failed for TX, trying internal RAM");
        tx_buffer = heap_caps_malloc(tx_size, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    }

    if (!rx_buffer || !tx_buffer) {
        ESP_LOGE(TAG, "Failed to allocate protocol buffers");
        if (rx_buffer) { heap_caps_free(rx_buffer); rx_buffer = NULL; }
        if (tx_buffer) { heap_caps_free(tx_buffer); tx_buffer = NULL; }
        return -1;
    }

    ESP_LOGI(TAG, "Protocol buffers allocated (RX: %p, TX: %p)", rx_buffer, tx_buffer);
    return 0;
}

size_t protocol_get_max_payload_size(void) {
    // Return effective max payload: minimum of protocol buffer and stream buffer
    size_t stream_buf_size = usb_transport_get_buffer_size();
    if (stream_buf_size > 0 && stream_buf_size < max_payload_size) {
        return stream_buf_size;
    }
    return max_payload_size;
}

void protocol_loop(void) {
    // Check if buffers were initialized
    if (!rx_buffer || !tx_buffer) {
        ESP_LOGE(TAG, "Protocol buffers not initialized, call protocol_init() first");
        // Try to initialize with defaults as fallback
        if (protocol_init(0, 0) != 0) {
            ESP_LOGE(TAG, "Failed to allocate buffers");
            return;
        }
    }

    ESP_LOGI(TAG, "Protocol loop started (max_payload=%u)", max_payload_size);

    while (1) {
        // 1. Sync: Look for Magic
        uint8_t byte;
        usb_read_bytes(&byte, 1);
        if (byte != MAGIC_BYTE_1) continue;
        
        usb_read_bytes(&byte, 1);
        if (byte != MAGIC_BYTE_2) continue;

        // 2. Read rest of header
        packet_header_t header;
        header.magic[0] = MAGIC_BYTE_1;
        header.magic[1] = MAGIC_BYTE_2;
        usb_read_bytes(&header.cmd_id, 1);
        usb_read_bytes(&header.flags, 1);
        usb_read_bytes((uint8_t*)&header.payload_len, 4);

        // 3. Read Payload
        if (header.payload_len > max_payload_size) {
            ESP_LOGE(TAG, "Payload too large: %lu (max: %u)", header.payload_len, max_payload_size);
            // Must drain payload + checksum to avoid protocol desync
            // Read in chunks to avoid stack overflow for very large payloads
            uint8_t drain_buf[256];
            size_t remaining = header.payload_len + 2;  // payload + 2-byte checksum
            while (remaining > 0) {
                size_t chunk = (remaining < sizeof(drain_buf)) ? remaining : sizeof(drain_buf);
                usb_read_bytes(drain_buf, chunk);
                remaining -= chunk;
            }
            ESP_LOGW(TAG, "Drained %lu bytes to resync", header.payload_len + 2);
            continue;
        }
        if (header.payload_len > 0) {
            usb_read_bytes(rx_buffer, header.payload_len);
        }

        // 4. Read Checksum
        uint16_t received_checksum;
        usb_read_bytes((uint8_t*)&received_checksum, 2);

        // 5. Verify Checksum
        uint16_t calc_checksum = calculate_checksum((uint8_t*)&header, sizeof(header));
        if (header.payload_len > 0) {
            calc_checksum += calculate_checksum(rx_buffer, header.payload_len);
        }

        if (calc_checksum != received_checksum) {
            ESP_LOGE(TAG, "Checksum mismatch: Calc %04X != Recv %04X", calc_checksum, received_checksum);
            // Send Error Response
            uint32_t err = ERR_CHECKSUM;
            send_response(header.cmd_id, 0x02, (uint8_t*)&err, 4);
            continue;
        }

        // 6. Dispatch
        ESP_LOGI(TAG, "Dispatching CMD: 0x%02X, Payload: %lu bytes", header.cmd_id, header.payload_len);
        uint32_t out_len = 0;
        uint32_t err_code = dispatch_command(header.cmd_id, rx_buffer, header.payload_len, tx_buffer, &out_len);

        if (err_code != ERR_OK) {
             ESP_LOGE(TAG, "Command failed with error: 0x%02X", err_code);
             send_response(header.cmd_id, 0x02, (uint8_t*)&err_code, 4);
        } else {
             ESP_LOGI(TAG, "Command success, sending response: %lu bytes", out_len);
             send_response(header.cmd_id, 0x01, tx_buffer, out_len);
        }
    }
}
