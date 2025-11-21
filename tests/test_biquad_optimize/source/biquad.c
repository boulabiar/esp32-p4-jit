#include <stdio.h>
#include <stdint.h>

typedef int esp_err_t;
#define ESP_OK 0

static inline uint32_t rdcycle(void) {
    uint32_t cycles;
    asm volatile ("rdcycle %0" : "=r"(cycles));
    return cycles;
}

esp_err_t dsps_biquad_f32(const float *input, float *output, int len, float *coef, float *w)
{
    for (int i = 0 ; i < len ; i++) {
        float d0 = input[i] - coef[3] * w[0] - coef[4] * w[1];
        output[i] = coef[0] * d0 +  coef[1] * w[0] + coef[2] * w[1];
        w[1] = w[0];
        w[0] = d0;
    }
    return ESP_OK;
}

uint32_t process_audio1(float *readBufferFloat, int readBufferLength, float *coeffs_lpf, float *w_lpf1, float *w_lpf2, float *w_lpf3)
{
    uint32_t start = rdcycle();
    
    dsps_biquad_f32(&readBufferFloat[4], &readBufferFloat[4], readBufferLength, coeffs_lpf, w_lpf1);
    dsps_biquad_f32(&readBufferFloat[4], &readBufferFloat[4], readBufferLength, coeffs_lpf, w_lpf2);
    dsps_biquad_f32(&readBufferFloat[4], &readBufferFloat[4], readBufferLength, coeffs_lpf, w_lpf3);
    
    uint32_t end = rdcycle();
    uint32_t cycles = end - start;
    
    return cycles;
}


uint32_t process_audio(float *readBufferFloat, int readBufferLength, float *coeffs_lpf, float *w_lpf1, float *w_lpf2, float *w_lpf3)
{
    // Warm-up: Load code and data into cache
    // Using 256 floats (1KB) which is safe for stack and matches readBufferLength
    float temp_buffer[256]; 
    
    // Initialize temp buffer to avoid optimizing it away (copy first 32 samples)
    for (int i = 0; i < 32; i++) {
        temp_buffer[i] = readBufferFloat[i + 4];
    }
    
    float w1_warmup[2] = {w_lpf1[0], w_lpf1[1]};
    float w2_warmup[2] = {w_lpf2[0], w_lpf2[1]};
    float w3_warmup[2] = {w_lpf3[0], w_lpf3[1]};
    
    volatile float coef_sum = coeffs_lpf[0] + coeffs_lpf[1] + coeffs_lpf[2] + coeffs_lpf[3] + coeffs_lpf[4];
    
    // Warmup run
    dsps_biquad_f32(temp_buffer, temp_buffer, readBufferLength, coeffs_lpf, w1_warmup);
    dsps_biquad_f32(temp_buffer, temp_buffer, readBufferLength, coeffs_lpf, w2_warmup);
    dsps_biquad_f32(temp_buffer, temp_buffer, readBufferLength, coeffs_lpf, w3_warmup);
    
    volatile float prevent_optimization = temp_buffer[0] + temp_buffer[255] + coef_sum;
    (void)prevent_optimization;

    // Pre-load the actual input buffer into cache
    volatile float dummy = 0;
    for(int i=0; i<readBufferLength; i++) {
        dummy += readBufferFloat[4+i];
    }
        
    // Actual measurement
    uint32_t start = rdcycle();
    
    dsps_biquad_f32(&readBufferFloat[4], &readBufferFloat[4], readBufferLength, coeffs_lpf, w_lpf1);
    dsps_biquad_f32(&readBufferFloat[4], &readBufferFloat[4], readBufferLength, coeffs_lpf, w_lpf2);
    dsps_biquad_f32(&readBufferFloat[4], &readBufferFloat[4], readBufferLength, coeffs_lpf, w_lpf3);
    
    uint32_t end = rdcycle();
    
    return end - start;
}


uint32_t process_audio3(float *readBufferFloat, int readBufferLength, float *coeffs_lpf, float *w_lpf1, float *w_lpf2, float *w_lpf3) {
    uint32_t start, end;
    for(int i =0; i<4; i++){
    /*
    asm volatile (
        "rdcycle %[start]\n\t"
        "fnmsub.s fa5, fa2, ft5, fa5\n\t"
        "fnmsub.s fa5, fa2, ft5, fa5\n\t"
        "fnmsub.s fa5, fa2, ft5, fa5\n\t"
        //"fnmsub.s fa1, fa3, fa6, fa6\n\t"
        "rdcycle %[end]\n\t"
        : [start] "=r" (start),
          [end] "=r" (end)
        :
        : "fa5"
    );
    */
    asm volatile (
        "rdcycle %[start]\n\t"
        "fnmsub.s fa5, fa2, ft5, fa5\n\t"
        "fnmsub.s fa6, fa3, ft6, fa6\n\t"
        "fnmsub.s fa7, fa4, ft7, fa7\n\t"
        "fnmsub.s ft0, ft1, ft2, ft0\n\t"
        "rdcycle %[end]\n\t"
        : [start] "=r" (start),
          [end] "=r" (end)
        :
        : "fa5", "fa6", "fa7", "ft0"
    );
    
    
    }
    
    return end - start;
}