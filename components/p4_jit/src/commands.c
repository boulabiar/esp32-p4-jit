#include "commands.h"
#include "protocol.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_cache.h"
#include <string.h>
#include <stdbool.h>

static const char *TAG = "commands";

// ============================================================================
// Device-side Allocation Tracking
// ============================================================================

#define MAX_ALLOCATIONS 64  // Maximum tracked allocations

typedef struct {
    uint32_t address;
    uint32_t size;
    bool in_use;
} allocation_entry_t;

static allocation_entry_t allocation_table[MAX_ALLOCATIONS] = {0};

/**
 * @brief Track a new allocation in the table.
 * @return true if tracked successfully, false if table is full
 */
static bool alloc_table_add(uint32_t address, uint32_t size) {
    for (int i = 0; i < MAX_ALLOCATIONS; i++) {
        if (!allocation_table[i].in_use) {
            allocation_table[i].address = address;
            allocation_table[i].size = size;
            allocation_table[i].in_use = true;
            ESP_LOGD(TAG, "Alloc tracked [%d]: addr=0x%08lX, size=%lu", i, address, size);
            return true;
        }
    }
    ESP_LOGW(TAG, "Allocation table full, cannot track 0x%08lX", address);
    return false;
}

/**
 * @brief Remove an allocation from the table.
 * @return true if found and removed, false if not found
 */
static bool alloc_table_remove(uint32_t address) {
    for (int i = 0; i < MAX_ALLOCATIONS; i++) {
        if (allocation_table[i].in_use && allocation_table[i].address == address) {
            allocation_table[i].in_use = false;
            allocation_table[i].address = 0;
            allocation_table[i].size = 0;
            ESP_LOGD(TAG, "Alloc removed [%d]: addr=0x%08lX", i, address);
            return true;
        }
    }
    ESP_LOGW(TAG, "Address 0x%08lX not found in allocation table", address);
    return false;
}

/**
 * @brief Check if an address range is within a tracked allocation.
 * @return true if the entire range [address, address+size) is valid
 */
static bool alloc_table_validate(uint32_t address, uint32_t size) {
    // Check for overflow (wraparound)
    if (size > 0 && address > UINT32_MAX - size) {
        ESP_LOGW(TAG, "Address range overflow detected: 0x%08lX + %lu", address, size);
        return false;
    }

    uint32_t end_addr = address + size;
    for (int i = 0; i < MAX_ALLOCATIONS; i++) {
        if (allocation_table[i].in_use) {
            uint32_t alloc_start = allocation_table[i].address;
            // Also check allocation end for overflow
            if (allocation_table[i].size > 0 &&
                alloc_start > UINT32_MAX - allocation_table[i].size) {
                continue;  // Skip malformed allocation
            }
            uint32_t alloc_end = alloc_start + allocation_table[i].size;
            if (address >= alloc_start && end_addr <= alloc_end) {
                return true;
            }
        }
    }
    return false;
}

/**
 * @brief Check if an address is the start of a tracked allocation.
 * @return true if address matches an allocation start
 */
static bool alloc_table_contains(uint32_t address) {
    for (int i = 0; i < MAX_ALLOCATIONS; i++) {
        if (allocation_table[i].in_use && allocation_table[i].address == address) {
            return true;
        }
    }
    return false;
}

// Helper structs for parsing payloads
#pragma pack(push, 1)
typedef struct {
    uint32_t size;
    // uint8_t memory_type; // Removed
    uint32_t caps;
    uint32_t alignment;
} cmd_alloc_req_t;

typedef struct {
    uint32_t address;
    uint32_t error_code;
} cmd_alloc_resp_t;

typedef struct {
    uint32_t address;
} cmd_free_req_t;

typedef struct {
    uint32_t address;
    uint8_t  flags;      // bit 0: skip_bounds (raw access)
    uint8_t  reserved[3];
    // data follows
} cmd_write_req_t;

typedef struct {
    uint32_t bytes_written;
    uint32_t status;
} cmd_write_resp_t;

typedef struct {
    uint32_t address;
    uint32_t size;
    uint8_t  flags;      // bit 0: skip_bounds (raw access)
    uint8_t  reserved[3];
} cmd_read_req_t;

// Request flags
#define REQ_FLAG_SKIP_BOUNDS 0x01

typedef struct {
    uint32_t address;
} cmd_exec_req_t;

typedef struct {
    uint32_t return_value;
} cmd_exec_resp_t;

typedef struct {
    uint32_t dummy; // Empty payload, but structs can't be empty in C standard sometimes, though GCC allows it.
                    // We'll just read 0 bytes payload.
} cmd_heap_info_req_t;

typedef struct {
    uint32_t free_spiram;
    uint32_t total_spiram;
    uint32_t free_internal;
    uint32_t total_internal;
} cmd_heap_info_resp_t;

typedef struct {
    uint8_t  protocol_version_major;
    uint8_t  protocol_version_minor;
    uint8_t  reserved[2];
    uint32_t max_payload_size;
    uint32_t cache_line_size;
    uint32_t max_allocations;
    char     firmware_version[16];  // Null-terminated string
} cmd_get_info_resp_t;
#pragma pack(pop)

// Firmware version string
#define FIRMWARE_VERSION "1.0.0"

uint32_t dispatch_command(uint8_t cmd_id, uint8_t *payload, uint32_t len, uint8_t *out_payload, uint32_t *out_len) {
    switch (cmd_id) {
        case CMD_PING:
            if (len > 0) memcpy(out_payload, payload, len);
            *out_len = len;
            return ERR_OK;

        case CMD_GET_INFO: {
            cmd_get_info_resp_t *resp = (cmd_get_info_resp_t*)out_payload;

            resp->protocol_version_major = PROTOCOL_VERSION_MAJOR;
            resp->protocol_version_minor = PROTOCOL_VERSION_MINOR;
            resp->reserved[0] = 0;
            resp->reserved[1] = 0;

            // Get actual max payload size from protocol layer
            size_t actual_max = protocol_get_max_payload_size();
            resp->max_payload_size = (actual_max > 0) ? actual_max : (1024 * 1024);

            // Get cache line size
            size_t cache_line = 0;
            esp_cache_get_alignment(MALLOC_CAP_SPIRAM, &cache_line);
            resp->cache_line_size = (cache_line > 0) ? cache_line : 64;

            resp->max_allocations = MAX_ALLOCATIONS;

            // Copy firmware version
            memset(resp->firmware_version, 0, sizeof(resp->firmware_version));
            strncpy(resp->firmware_version, FIRMWARE_VERSION, sizeof(resp->firmware_version) - 1);

            ESP_LOGI(TAG, "CMD_GET_INFO: Protocol v%d.%d, FW %s, MaxPayload=%lu, CacheLine=%lu",
                     resp->protocol_version_major, resp->protocol_version_minor,
                     resp->firmware_version, resp->max_payload_size, resp->cache_line_size);

            *out_len = sizeof(cmd_get_info_resp_t);
            return ERR_OK;
        }

        case CMD_ALLOC: {
            if (len < sizeof(cmd_alloc_req_t)) {
                ESP_LOGE(TAG, "CMD_ALLOC: Payload too short (%lu)", len);
                return ERR_UNKNOWN_CMD;
            }
            cmd_alloc_req_t *req = (cmd_alloc_req_t*)payload;

            ESP_LOGI(TAG, "CMD_ALLOC: Size=%lu, Caps=0x%08lX, Align=%lu",
                     req->size, req->caps, req->alignment);

            // Validate alignment: must be non-zero and power of two
            if (req->alignment == 0 || (req->alignment & (req->alignment - 1)) != 0) {
                ESP_LOGE(TAG, "CMD_ALLOC: Invalid alignment %lu (must be non-zero power of two)", req->alignment);
                cmd_alloc_resp_t *resp = (cmd_alloc_resp_t*)out_payload;
                resp->address = 0;
                resp->error_code = ERR_ALLOC_FAIL;
                *out_len = sizeof(cmd_alloc_resp_t);
                return ERR_OK;
            }

            void *ptr = heap_caps_aligned_alloc(req->alignment, req->size, req->caps);

            cmd_alloc_resp_t *resp = (cmd_alloc_resp_t*)out_payload;

            if (ptr) {
                // Track allocation in table
                if (!alloc_table_add((uint32_t)ptr, req->size)) {
                    // Table full - free memory and fail
                    ESP_LOGE(TAG, "CMD_ALLOC: Allocation table full");
                    heap_caps_free(ptr);
                    resp->address = 0;
                    resp->error_code = ERR_ALLOC_FAIL;
                } else {
                    ESP_LOGI(TAG, "CMD_ALLOC: Success at %p", ptr);
                    resp->address = (uint32_t)ptr;
                    resp->error_code = 0;
                }
            } else {
                ESP_LOGE(TAG, "CMD_ALLOC: Failed");
                resp->address = 0;
                resp->error_code = ERR_ALLOC_FAIL;
            }

            *out_len = sizeof(cmd_alloc_resp_t);
            return ERR_OK;
        }

        case CMD_FREE: {
            if (len < sizeof(cmd_free_req_t)) return ERR_UNKNOWN_CMD;
            cmd_free_req_t *req = (cmd_free_req_t*)payload;

            // Validate address is in allocation table
            if (!alloc_table_contains(req->address)) {
                ESP_LOGE(TAG, "CMD_FREE: Address 0x%08lX not in allocation table", req->address);
                uint32_t *status = (uint32_t*)out_payload;
                *status = ERR_INVALID_ADDR;
                *out_len = 4;
                return ERR_INVALID_ADDR;
            }

            // Remove from tracking and free
            alloc_table_remove(req->address);
            heap_caps_free((void*)req->address);

            uint32_t *status = (uint32_t*)out_payload;
            *status = 0;
            *out_len = 4;
            return ERR_OK;
        }

        case CMD_WRITE_MEM: {
            // Protocol v1.0 format: address(4) + flags(1) + reserved(3) + data
            if (len < sizeof(cmd_write_req_t)) return ERR_UNKNOWN_CMD;

            cmd_write_req_t *req = (cmd_write_req_t*)payload;
            uint32_t address = req->address;
            uint8_t flags = req->flags;
            uint32_t data_len = len - sizeof(cmd_write_req_t);
            uint8_t *data_ptr = payload + sizeof(cmd_write_req_t);

            // Validate address range unless skip_bounds is set
            bool skip_bounds = (flags & REQ_FLAG_SKIP_BOUNDS) != 0;
            if (!skip_bounds && !alloc_table_validate(address, data_len)) {
                ESP_LOGE(TAG, "CMD_WRITE_MEM: Address 0x%08lX (len=%lu) not in valid allocation", address, data_len);
                cmd_write_resp_t *resp = (cmd_write_resp_t*)out_payload;
                resp->bytes_written = 0;
                resp->status = ERR_INVALID_ADDR;
                *out_len = sizeof(cmd_write_resp_t);
                return ERR_INVALID_ADDR;
            }

            memcpy((void*)address, data_ptr, data_len);

            // Sync Cache (D-Cache -> RAM -> I-Cache)
            // esp_cache_msync requires address and size to be aligned to cache line size
            size_t cache_line_size = 0;
            esp_cache_get_alignment(MALLOC_CAP_SPIRAM, &cache_line_size);
            if (cache_line_size == 0) {
                cache_line_size = 64;  // Fallback default
            }

            uint32_t start_addr = address;
            uint32_t end_addr = start_addr + data_len;

            uint32_t aligned_start = start_addr & ~(cache_line_size - 1);
            uint32_t aligned_end = (end_addr + cache_line_size - 1) & ~(cache_line_size - 1);
            uint32_t aligned_size = aligned_end - aligned_start;
            
            ESP_LOGI(TAG, "Cache Sync: Orig Addr=0x%08lX, Len=0x%lX -> Aligned Addr=0x%08lX, Len=0x%lX",
                     address, data_len, aligned_start, aligned_size);

            esp_err_t err = esp_cache_msync((void*)aligned_start, aligned_size, 
                                          ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_INVALIDATE);
            if (err != ESP_OK) {
                ESP_LOGE(TAG, "Cache sync failed: 0x%x", err);
            }

            cmd_write_resp_t *resp = (cmd_write_resp_t*)out_payload;
            resp->bytes_written = data_len;
            resp->status = (err == ESP_OK) ? 0 : 1;
            *out_len = sizeof(cmd_write_resp_t);
            return ERR_OK;
        }

        case CMD_READ_MEM: {
            // Protocol v1.0 format: address(4) + size(4) + flags(1) + reserved(3)
            if (len < sizeof(cmd_read_req_t)) return ERR_UNKNOWN_CMD;

            cmd_read_req_t *req = (cmd_read_req_t*)payload;
            uint32_t address = req->address;
            uint32_t size = req->size;
            uint8_t flags = req->flags;

            // Bounds check: prevent TX buffer overflow using actual configured size
            size_t max_read = protocol_get_max_payload_size();
            if (max_read == 0) max_read = 1024 * 1024;  // Fallback default

            if (size > max_read) {
                ESP_LOGE(TAG, "CMD_READ_MEM: Requested size %lu exceeds max %u", size, max_read);
                return ERR_UNKNOWN_CMD;
            }

            // Validate address range unless skip_bounds is set
            bool skip_bounds = (flags & REQ_FLAG_SKIP_BOUNDS) != 0;
            if (!skip_bounds && !alloc_table_validate(address, size)) {
                ESP_LOGE(TAG, "CMD_READ_MEM: Address 0x%08lX (len=%lu) not in valid allocation", address, size);
                return ERR_INVALID_ADDR;
            }

            memcpy(out_payload, (void*)address, size);

            *out_len = size;
            return ERR_OK;
        }

        case CMD_EXEC: {
            if (len < sizeof(cmd_exec_req_t)) return ERR_UNKNOWN_CMD;
            cmd_exec_req_t *req = (cmd_exec_req_t*)payload;

            // Validate address is within a tracked allocation
            // We check for at least 1 byte (the function must start in valid memory)
            if (!alloc_table_validate(req->address, 1)) {
                ESP_LOGE(TAG, "CMD_EXEC: Address 0x%08lX not in valid allocation", req->address);
                cmd_exec_resp_t *resp = (cmd_exec_resp_t*)out_payload;
                resp->return_value = 0xDEADBEEF;  // Sentinel for invalid exec
                *out_len = sizeof(cmd_exec_resp_t);
                return ERR_INVALID_ADDR;
            }

            // Cast and call
            typedef int (*jit_func_t)(void);
            jit_func_t func = (jit_func_t)req->address;

            ESP_LOGI(TAG, "Executing at 0x%08lX", req->address);
            int ret = func();
            ESP_LOGI(TAG, "Returned: %d", ret);

            cmd_exec_resp_t *resp = (cmd_exec_resp_t*)out_payload;
            resp->return_value = ret;
            *out_len = sizeof(cmd_exec_resp_t);
            return ERR_OK;
        }

        case CMD_HEAP_INFO: {
            // No request payload needed
            
            cmd_heap_info_resp_t *resp = (cmd_heap_info_resp_t*)out_payload;
            
            resp->free_spiram = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
            resp->total_spiram = heap_caps_get_total_size(MALLOC_CAP_SPIRAM);
            
            resp->free_internal = heap_caps_get_free_size(MALLOC_CAP_INTERNAL);
            resp->total_internal = heap_caps_get_total_size(MALLOC_CAP_INTERNAL);
            
            ESP_LOGI(TAG, "Heap Info: SPIRAM: %lu/%lu, INT: %lu/%lu",
                     resp->free_spiram, resp->total_spiram,
                     resp->free_internal, resp->total_internal);
            
            *out_len = sizeof(cmd_heap_info_resp_t);
            return ERR_OK;
        }

        default:
            ESP_LOGW(TAG, "Unknown command: 0x%02X", cmd_id);
            return ERR_UNKNOWN_CMD;
    }
}
