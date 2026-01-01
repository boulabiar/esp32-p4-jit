#include <stdio.h>
#include <cstring>
#include <vector> // Added for std::vector iteration
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "dl_model_base.hpp"
#include "dl_math.hpp"

static const char *TAG = "app_wrapper";

// =============================================================================
// GLOBAL STATE (Exposed to Python via JIT)
// =============================================================================
// The Model Instantiation
dl::Model *G_MODEL = nullptr;

// The Raw Model Binary (Uploaded by Python to PSRAM)
void *G_MODEL_BUFFER = nullptr; 

// Tensor Pointers (Set after Model Init)
int8_t *G_INPUT_TENSOR = nullptr;
int8_t *G_OUTPUT_TENSOR = nullptr;
int G_INPUT_EXPONENT = 0;
int G_OUTPUT_EXPONENT = 0;

// =============================================================================
// CONTROL API (Called by Python)
// =============================================================================

extern "C" {

/**
 * @brief Initialize the Model using raw .espdl bytes already in RAM.
 * @param model_data Pointer to the .espdl binary in PSRAM.
 */
void app_model_init_from_ram(void *model_data) {
    if (G_MODEL) {
        ESP_LOGW(TAG, "Model already initialized. Delete old?");
        // delete G_MODEL; // Optional: implement cleanup
    }
    
    ESP_LOGI(TAG, "Initializing DL Model from RAM: %p", model_data);
    G_MODEL_BUFFER = model_data;

    // 1. Create Model (Parsing Flatbuffers)
    // Use MODEL_LOCATION_IN_FLASH_RODATA for memory-mapped pointers (works for PSRAM too)
    G_MODEL = new dl::Model((const char *)G_MODEL_BUFFER, fbs::MODEL_LOCATION_IN_FLASH_RODATA);

    if (!G_MODEL) {
        ESP_LOGE(TAG, "Failed to create dl::Model");
        return;
    }

    // 2. Extract Tensor Pointers for easy access
    std::map<std::string, dl::TensorBase *> model_inputs = G_MODEL->get_inputs();
    dl::TensorBase *in_t = model_inputs.begin()->second;
    G_INPUT_TENSOR = (int8_t *)in_t->data;
    G_INPUT_EXPONENT = in_t->exponent;

    std::map<std::string, dl::TensorBase *> model_outputs = G_MODEL->get_outputs();
    dl::TensorBase *out_t = model_outputs.begin()->second;
    G_OUTPUT_TENSOR = (int8_t *)out_t->data;
    G_OUTPUT_EXPONENT = out_t->exponent;
    ESP_LOGI(TAG, "Model Loaded!");
    ESP_LOGI(TAG, "Input Tensor: %p (Exp: %d)", G_INPUT_TENSOR, in_t->exponent);
    
    printf("DEBUG: Input Dims: [");
    for (int i = 0; i < in_t->shape.size(); i++) printf("%d ", in_t->shape[i]);
    printf("]\n");

    ESP_LOGI(TAG, "Output Tensor: %p (Exp: %d)", G_OUTPUT_TENSOR, out_t->exponent);

    printf("DEBUG: Output Dims: [");
    for (int i = 0; i < out_t->shape.size(); i++) printf("%d ", out_t->shape[i]);
    printf("]\n");

    // [Inside app_model_init_from_ram] after printing diff
    
    // FIX: Allocate a Safe Input Buffer if potentially overlapping
    // The Greedy Allocator might place Input/Output/Intermediates close.
    // To assume safety, we allocate a dedicated buffer for the Input.
    int input_size = in_t->get_bytes(); // Should be ~49152
    if (input_size > 0) {
        void* safe_input = heap_caps_malloc(input_size, MALLOC_CAP_SPIRAM);
        if (safe_input) {
            ESP_LOGW(TAG, "Allocated Safe Input Buffer: %p (%d bytes)", safe_input, input_size);
            in_t->set_element_ptr(safe_input);
            G_INPUT_TENSOR = (int8_t*)safe_input;
        } else {
            ESP_LOGE(TAG, "Failed to allocate Safe Input Buffer!");
        }
    }
}

/**
 * @brief Run Standard Preprocessing (Norm -> Quantize)
 */
void app_preprocess_from_buffer(uint8_t *raw_rgb, int width, int height, float *mean, float *std) {
    if (!G_INPUT_TENSOR) {
         ESP_LOGE(TAG, "G_INPUT_TENSOR is NULL!");
         return;
    }

    int num_pixels = width * height * 3;
    
    // Simple Loop (SIMD-capable if enabled)
    for (int i = 0; i < num_pixels; i++) {
        int ch = i % 3;
        float val = (float)raw_rgb[i];
        float norm = (val / 255.0f - mean[ch]) / std[ch];
        G_INPUT_TENSOR[i] = dl::quantize<int8_t>(norm, DL_RESCALE(G_INPUT_EXPONENT));
    }
}

/**
 * @brief Trigger Inference
 */
void app_model_run(void) {
    if (G_MODEL) {
        int64_t start = esp_timer_get_time();
        G_MODEL->run();
        int64_t end = esp_timer_get_time();
        ESP_LOGI(TAG, "Inference Done: %lld us", (end - start));
    } else {
        ESP_LOGE(TAG, "No Model loaded!");
    }
}

/**
 * @brief Helper to Dequantize Output (for simple checks)
 */
float app_get_score(int index) {
    if (!G_OUTPUT_TENSOR) return -1.0f;
    return dl::dequantize(G_OUTPUT_TENSOR[index], DL_SCALE(G_OUTPUT_EXPONENT));
}

} // extern "C"
