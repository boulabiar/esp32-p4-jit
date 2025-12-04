#include <stdint.h>

/**
 * Test function to verify Smart Args type handling.
 * 
 * It takes various types, sums them up (casting to int32), and adds the sum of the array.
 * 
 * @param a int8_t (scalar)
 * @param b uint8_t (scalar)
 * @param c int16_t (scalar)
 * @param d uint16_t (scalar)
 * @param e int32_t (scalar)
 * @param f float (scalar)
 * @param array_in pointer to int32_t array
 * @param len length of array
 * @return Sum of all inputs cast to int32_t
 */
int32_t test_all_types(int8_t a, uint8_t b, int16_t c, uint16_t d, int32_t e, float f, int32_t* array_in, int32_t len) {
    int32_t sum = 0;
    
    sum += (int32_t)a;
    sum += (int32_t)b;
    sum += (int32_t)c;
    sum += (int32_t)d;
    sum += e;
    sum += (int32_t)f; // Truncate float
    
    for (int i = 0; i < len; i++) {
        sum += array_in[i];
    }
    
    return sum;
}
