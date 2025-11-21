import sys
import os
import struct
import time
import numpy as np
import math

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from esp32_loader import Builder
from p4_jit import JITSession
from p4_jit.memory_caps import *

print("--- P4-JIT Biquad Filter Test (Verified) ---")

# --- Python Implementation for Verification ---
def calculate_coefficients(fc, fs, Q):
    """Calculate RBJ Biquad LPF coefficients."""
    w0 = 2 * math.pi * fc / fs
    alpha = math.sin(w0) / (2 * Q)
    cos_w0 = math.cos(w0)

    b0 = (1 - cos_w0) / 2
    b1 = 1 - cos_w0
    b2 = (1 - cos_w0) / 2
    a0 = 1 + alpha
    a1 = -2 * cos_w0
    a2 = 1 - alpha

    # Normalize by a0
    return np.array([b0/a0, b1/a0, b2/a0, a1/a0, a2/a0], dtype=np.float32)

def python_biquad(input_arr, coef, w):
    """
    Python implementation of Direct Form II Biquad.
    Matches the C implementation:
    d0 = input[i] - coef[3] * w[0] - coef[4] * w[1];
    output[i] = coef[0] * d0 +  coef[1] * w[0] + coef[2] * w[1];
    w[1] = w[0];
    w[0] = d0;
    """
    output_arr = np.zeros_like(input_arr)
    for i in range(len(input_arr)):
        d0 = input_arr[i] - coef[3] * w[0] - coef[4] * w[1]
        output_arr[i] = coef[0] * d0 + coef[1] * w[0] + coef[2] * w[1]
        w[1] = w[0]
        w[0] = d0
    return output_arr

# ----------------------------------------------

# 1. Connect
print("1. Connecting to device...")
session = JITSession()
try:
    session.connect()
except Exception as e:
    print(f"Error connecting: {e}")
    sys.exit()

# 2. Prepare Data
print("2. Preparing Data...")

# Parameters
Fs = 48000.0
Fc = 1000.0
Q = 0.707
Len = 32

# Generate Coefficients
coeffs_lpf = calculate_coefficients(Fc, Fs, Q)
print(f"   Coefficients (LPF @ {Fc}Hz): {coeffs_lpf}")

# Generate Input Signal (Sine Wave + DC offset to verify filtering)
t = np.arange(Len) / Fs
# 1kHz sine wave (passband) + 10kHz sine wave (stopband)
input_signal = np.sin(2 * np.pi * 1000 * t) + 0.5 * np.sin(2 * np.pi * 10000 * t)
input_signal = input_signal.astype(np.float32)

# Prepare Buffer (Size 36, offset 4)
# We place the signal starting at index 4
readBufferFloat = np.zeros(36, dtype=np.float32)
readBufferFloat[4:4+Len] = input_signal

readBufferLength = np.int32(Len)

# State variables (3 stages)
w_lpf1 = np.zeros(2, dtype=np.float32)
w_lpf2 = np.zeros(2, dtype=np.float32)
w_lpf3 = np.zeros(2, dtype=np.float32)

# --- Run Python Verification ---
print("   Running Python Simulation...")
py_buffer = readBufferFloat.copy()
py_signal = py_buffer[4:4+Len]

# Simulate 3 cascaded stages
# Stage 1
w1_py = np.zeros(2, dtype=np.float32)
py_signal = python_biquad(py_signal, coeffs_lpf, w1_py)
# Stage 2
w2_py = np.zeros(2, dtype=np.float32)
py_signal = python_biquad(py_signal, coeffs_lpf, w2_py)
# Stage 3
w3_py = np.zeros(2, dtype=np.float32)
py_signal = python_biquad(py_signal, coeffs_lpf, w3_py)

# Update buffer with result
py_buffer[4:4+Len] = py_signal
expected_result = py_buffer

# -------------------------------

# 3. Build JIT Function
print("3. Building JIT Function...")
builder = Builder()
source_dir = os.path.join(os.path.dirname(__file__), 'source')
main_source = os.path.join(source_dir, 'biquad.c')

# Pass 1: Probe
print("   Pass 1: Probing...")
temp_bin = builder.wrapper.build_with_wrapper(
    source=main_source,
    function_name='process_audio',
    base_address=0x03000004,
    arg_address=0x00030004
)

code_size = temp_bin.total_size
args_size = temp_bin.metadata['addresses']['args_array_bytes']

# Allocate Code & Args
CAP_EXEC = MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT 
CAP_DATA = MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT

code_addr = session.device.allocate(code_size + 64, caps=CAP_EXEC, alignment=128)
args_addr = session.device.allocate(args_size, caps=CAP_DATA, alignment=128)

print(f"   Code Allocated at: 0x{code_addr:08X}")
print(f"   Args Allocated at: 0x{args_addr:08X}")

# Pass 2: Final Build
print("   Pass 2: Final Compilation...")
final_bin = builder.wrapper.build_with_wrapper(
    source=main_source,
    function_name='process_audio',
    base_address=code_addr,
    arg_address=args_addr
)

# Upload Code
print("   Uploading binary...")
remote_func = session.load_function(final_bin, args_addr, smart_args=False)

# 4. Manual Memory Allocation
print("4. Allocating Device Memory...")

def allocate_and_write(arr):
    size_bytes = arr.nbytes
    addr = session.device.allocate(size_bytes, CAP_DATA, 16)
    session.device.write_memory(addr, arr.tobytes())
    return addr

addr_readBuffer = allocate_and_write(readBufferFloat)
addr_coeffs = allocate_and_write(coeffs_lpf)
addr_w1 = allocate_and_write(w_lpf1)
addr_w2 = allocate_and_write(w_lpf2)
addr_w3 = allocate_and_write(w_lpf3)

# 5. Execute
print("5. Executing process_audio on Device...")

args_packed = struct.pack(
    "<IiIIII", 
    addr_readBuffer, 
    int(readBufferLength), 
    addr_coeffs, 
    addr_w1, 
    addr_w2, 
    addr_w3
)

start_time = time.time()
remote_func(args_packed)
end_time = time.time()

print(f"   Time: {(end_time - start_time)*1000:.2f} ms")

# 6. Verify
print("6. Verifying Result...")
result_bytes = session.device.read_memory(addr_readBuffer, readBufferFloat.nbytes)
result_array = np.frombuffer(result_bytes, dtype=np.float32)

print("   Input Signal (First 5):", input_signal[:5])
print("   Python Result (First 5):", expected_result[4:9])
print("   Device Result (First 5):", result_array[4:9])

# Compare
# Allow small tolerance due to float precision differences
if np.allclose(result_array, expected_result, atol=1e-5):
    print("SUCCESS: Device output matches Python simulation!")
else:
    print("FAILURE: Output mismatch!")
    diff = np.abs(result_array - expected_result)
    print(f"   Max Diff: {np.max(diff)}")
    print(f"   Mean Diff: {np.mean(diff)}")

# 7. Cleanup
print("7. Cleaning up...")
session.device.free(code_addr)
session.device.free(args_addr)
session.device.free(addr_readBuffer)
session.device.free(addr_coeffs)
session.device.free(addr_w1)
session.device.free(addr_w2)
session.device.free(addr_w3)
session.device.disconnect()

final_bin.disassemble("asm.txt", False)
