#ifndef BIQUAD_H
#define BIQUAD_H

// Auto-generated header for process_audio
// Source: biquad.c


// Function declaration
uint32_t process_audio(float* readBufferFloat, int readBufferLength, float* coeffs_lpf, float* w_lpf1, float* w_lpf2, float* w_lpf3);

#endif // BIQUAD_H
