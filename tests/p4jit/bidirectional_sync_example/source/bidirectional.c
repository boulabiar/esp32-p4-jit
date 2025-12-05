#include <stdint.h>
// Simple function to modify an array in-place and return the first element
// Used to test bidirectional data flow and return values
int modify_array(int* data, int len) {
    for(int i = 0; i < len; i++) {
        data[i] = data[i] * 2;
    }
    return data[0];
}
