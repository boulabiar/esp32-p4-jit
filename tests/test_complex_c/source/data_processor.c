#include "data_processor.h"
#include "math_utils.h"

void process_element(int *val, float scale, float offset) {
    float v = (float)*val;
    
    // Complex operation: |(v * scale)^2 + offset|
    v = v * scale;
    v = custom_pow(v, 2);
    v = v + offset;
    v = custom_abs(v);
    
    *val = (int)v;
}
