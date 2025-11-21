#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "usb_transport.h"
#include "protocol.h"

static const char *TAG = "main";

void app_main(void)
{
    ESP_LOGI(TAG, "Starting P4-JIT Firmware");

    // 1. Initialize USB Transport
    ESP_LOGI(TAG, "Initializing USB Transport...");
    usb_transport_init();

    // 2. Enter Protocol Loop
    ESP_LOGI(TAG, "Entering Protocol Loop...");
    protocol_loop();
}
