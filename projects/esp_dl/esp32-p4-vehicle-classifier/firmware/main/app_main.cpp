#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "esp_log.h"
#include "p4_jit.h"  

static const char *TAG = "app_main";

extern "C" void app_main(void)
{

    ESP_LOGI(TAG, "Starting P4-JIT Vehicle Classifier Node...");

    // 2. Start JIT Server
    esp_err_t err = p4_jit_start(NULL);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start JIT: %d", err);
    }

    ESP_LOGI(TAG, "Firmware Ready. Waiting for Notebook commands...");

    // 3. Idle Loop
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));
        // Optional: blink LED or print heartbeat
    }
}
