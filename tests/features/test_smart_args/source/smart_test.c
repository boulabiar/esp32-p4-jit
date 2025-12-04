#include <stdint.h>

int smart_test(int *arr, int len, float scale) {
    float sum = 0;
    for(int i = 0; i < len; i++) {
        sum += arr[i];
    }
    return (int)(sum * scale);
}
