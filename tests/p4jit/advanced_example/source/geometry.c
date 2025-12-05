#include <stdint.h>

typedef struct {
    float x;
    int y;
} Point;

float sum_point(Point* p, int8_t z, uint16_t* arr) {
    return p->x + (float)p->y + (float)z + (float)arr[0];
}
