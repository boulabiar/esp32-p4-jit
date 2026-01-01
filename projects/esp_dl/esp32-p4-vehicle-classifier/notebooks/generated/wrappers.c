
#include <stdint.h>
#include <stdio.h>

// Firmware API Declarations
extern void app_model_init_from_ram(void *ptr);
extern void app_preprocess_from_buffer(uint8_t *raw, int w, int h, float *mean, float *std);
extern void app_model_run(void);
extern float app_get_score(int idx);

// Variables to peek at from JIT
extern int G_INPUT_EXPONENT;
extern int G_OUTPUT_EXPONENT;
extern int8_t *G_INPUT_TENSOR;

// JIT Wrappers
void jit_init(int ptr) {
    printf("JIT DEBUG: Calling Init with ptr: 0x%x\n", ptr);
    app_model_init_from_ram((void*)ptr);
    printf("JIT DEBUG: Initialized. Input Exponent: %d\n", G_INPUT_EXPONENT);
}

void jit_preprocess(int raw_addr, int w, int h, float *mean, float *std) {
    uint8_t* raw = (uint8_t*)raw_addr;
    printf("JIT DEBUG: Preprocessing %dx%d image at 0x%x\n", w, h, raw_addr);
    
    app_preprocess_from_buffer(raw, w, h, mean, std);
    
    if (G_INPUT_TENSOR) {
        printf("JIT DEBUG: First 3 Quantized Tensor Vals: %d %d %d\n", 
               G_INPUT_TENSOR[0], G_INPUT_TENSOR[1], G_INPUT_TENSOR[2]);
    } else {
        printf("JIT DEBUG: ERROR - G_INPUT_TENSOR is NULL!\n");
    }
}

void jit_run(void) {
    app_model_run();
}

float jit_get_score(int idx) {
    return app_get_score(idx);
}
