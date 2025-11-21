#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_psram.h"
#include "esp_heap_caps.h"
#include "tinyusb.h"
#include "tinyusb_cdc_acm.h"

#define ARRAY_SIZE 1024 * 1024
#define TAG "USB_TEST"

static int8_t* psram_buffer = NULL;
static volatile size_t bytes_received = 0;
static volatile bool transfer_complete = false;

static void rx_callback(int itf, cdcacm_event_t *event) {
    size_t rx_size = 0;
    uint8_t buf[CONFIG_TINYUSB_CDC_RX_BUFSIZE];
    
    tinyusb_cdcacm_read(itf, buf, CONFIG_TINYUSB_CDC_RX_BUFSIZE, &rx_size);
    
    if (bytes_received + rx_size <= ARRAY_SIZE) {
        memcpy(psram_buffer + bytes_received, buf, rx_size);
        bytes_received += rx_size;
        
        if (bytes_received >= ARRAY_SIZE) {
            transfer_complete = true;
        }
    }
}

static int32_t compute_sum(int8_t* data, size_t len) {
    int32_t sum = 0;
    for (size_t i = 0; i < len; i++) {
        sum += data[i];
    }
    return sum;
}

static void send_result(int32_t sum) {
    char result[32];
    int len = snprintf(result, sizeof(result), "%ld\n", sum);
    tinyusb_cdcacm_write_queue(TINYUSB_CDC_ACM_0, (uint8_t*)result, len);
    tinyusb_cdcacm_write_flush(TINYUSB_CDC_ACM_0, 0);
}

static void init_psram_buffer(void) {
    psram_buffer = (int8_t*)heap_caps_malloc(ARRAY_SIZE, MALLOC_CAP_SPIRAM);
    if (psram_buffer == NULL) {
        ESP_LOGE(TAG, "Failed to allocate PSRAM buffer");
        abort();
    }
    ESP_LOGI(TAG, "PSRAM buffer allocated at %p", psram_buffer);
}

static void init_usb(void) {
    const tinyusb_config_t tusb_cfg = {
        .port = TINYUSB_PORT_HIGH_SPEED_0,  // Use High-Speed port
        .task = {
            .size = 4096,
            .priority = 5,
            .xCoreID = 0,
        },
    };
    
    ESP_ERROR_CHECK(tinyusb_driver_install(&tusb_cfg));
    
    tinyusb_config_cdcacm_t acm_cfg = {
        .cdc_port = TINYUSB_CDC_ACM_0,
        .callback_rx = &rx_callback,
        .callback_rx_wanted_char = NULL,
        .callback_line_state_changed = NULL,
        .callback_line_coding_changed = NULL
    };
    
    ESP_ERROR_CHECK(tinyusb_cdcacm_init(&acm_cfg));
    ESP_LOGI(TAG, "USB CDC-ACM initialized");
}

void app_main(void) {
    init_psram_buffer();
    init_usb();
    
    ESP_LOGI(TAG, "Waiting for data...");
    
    while (1) {
        if (transfer_complete) {
            ESP_LOGI(TAG, "Transfer complete: %d bytes", bytes_received);
            
            int32_t sum = compute_sum(psram_buffer, ARRAY_SIZE);
            ESP_LOGI(TAG, "Sum: %ld", sum);
            
            send_result(sum);
            
            bytes_received = 0;
            transfer_complete = false;
            
            ESP_LOGI(TAG, "Ready for next transfer");
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}