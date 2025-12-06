#ifndef MNIST_INFERENCE_H
#define MNIST_INFERENCE_H

// Auto-generated header for mnist_inference
// Source: mnist_inference.c

#include "std_types.h"

// Function declaration
int32_t mnist_inference(int8_t* input, int8_t* w_conv1, int8_t* b_conv1, int8_t* w_conv2, int8_t* b_conv2, int8_t* w_fc1, int8_t* b_fc1, int8_t* w_fc2, int8_t* b_fc2, int32_t e_in, int32_t e_conv1_w, int32_t e_conv1_act, int32_t e_conv2_w, int32_t e_conv2_act, int32_t e_fc1_w, int32_t e_fc1_act, int32_t e_fc2_w, int8_t* scratch, uint32_t* timing);

#endif // MNIST_INFERENCE_H
