#include "math_utils.h"

float custom_pow(float base, int exp) {
    float res = 1.0f;
    for (int i = 0; i < exp; i++) {
        res *= base;
    }
    return res;
}

float custom_abs(float val) {
    if (val < 0) return -val;
    return val;
}
