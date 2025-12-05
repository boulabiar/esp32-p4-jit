#include <stdint.h>

/**
 * Applies a gain factor to an array of audio samples (8-bit).
 * 
 * @param data Pointer to audio data (uint8_t)
 * @param len Length of the array
 * @param gain Gain factor (float)
 * @return The gain factor used (just to return something)
 */
float apply_gain(uint8_t* data, int len, float gain) {
    for(int i=0; i<len; i++) {
        // Simple clipping logic
        float val = (float)data[i] * gain;
        if (val > 255.0f) val = 255.0f;
        data[i] = (uint8_t)val;
    }
    return gain;
}
