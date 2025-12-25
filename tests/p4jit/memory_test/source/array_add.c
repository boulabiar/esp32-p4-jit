
#include <stdint.h>

// Function: array_add_accumulate
// Adds all elements of the array and stores the result in arr[0]
// Returns the result as well.
int array_add_accumulate(int32_t *arr, int len) {
    int sum = 0;
    for (int i = 0; i < len; i++) {
        sum += arr[i];
    }
    
    // Store result in first position
    if (len > 0) {
        arr[0] = sum;
    }
    
    return sum;
}
