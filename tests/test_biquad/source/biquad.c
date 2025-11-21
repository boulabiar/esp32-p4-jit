#include <stdio.h>

typedef int esp_err_t;
#define ESP_OK 0

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

void process_audio(float *readBufferFloat, int readBufferLength, float *coeffs_lpf, float *w_lpf1, float *w_lpf2, float *w_lpf3)
{
    dsps_biquad_f32(&readBufferFloat[4], &readBufferFloat[4], readBufferLength, coeffs_lpf, w_lpf1);
    dsps_biquad_f32(&readBufferFloat[4], &readBufferFloat[4], readBufferLength, coeffs_lpf, w_lpf2);
    dsps_biquad_f32(&readBufferFloat[4], &readBufferFloat[4], readBufferLength, coeffs_lpf, w_lpf3);
}

