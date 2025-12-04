#include "data_processor.h"

// Entry point
// args:
//  data: int array (modified in place)
//  len: length of array
//  scale: float multiplier
//  offset: float offset
int complex_c_test(int *data, int len, float scale, float offset) {
    int sum = 0;
    
    for(int i = 0; i < len; i++) {
        process_element(&data[i], scale, offset);
        sum += data[i];
    }
    
    return sum;
}
