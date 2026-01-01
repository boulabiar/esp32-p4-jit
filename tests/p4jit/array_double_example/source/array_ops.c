
#include <stdint.h>

/**
 * Doubles every element in the array and returns the sum of the doubled values.
 * 
 * @param array Pointer to the array of integers
 * @param length Number of elements in the array
 * @return Sum of all elements after doubling
 */
int double_and_sum(int* array, int length) {
    int sum = 0;
    for (int i = 0; i < length; i++) {
        array[i] = array[i] * 2;
        sum += array[i];
    }
    return sum;
}
