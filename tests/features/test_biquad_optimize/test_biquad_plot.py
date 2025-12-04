import sys
import os
import struct
import time
import numpy as np
import math
import matplotlib.pyplot as plt

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'host')))

from p4jit.toolchain import Builder
from p4jit.runtime import JITSession
from p4jit.runtime.memory_caps import *

print("--- P4-JIT Biquad Filter Test (Visual) ---")

# --- Helper Functions ---
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

    return np.array([b0/a0, b1/a0, b2/a0, a1/a0, a2/a0], dtype=np.float32)

# ------------------------

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
Len = 256 # Increased length to see the waveform better

# Generate Coefficients
coeffs_lpf = calculate_coefficients(Fc, Fs, Q)
print(f"   Coefficients (LPF @ {Fc}Hz): {coeffs_lpf}")

# Generate Input Signal
t = np.arange(Len) / Fs
# 1kHz sine (pass) + 10kHz sine (stop)
input_signal = np.sin(2 * np.pi * 1000 * t) + 0.5 * np.sin(2 * np.pi * 10000 * t)
input_signal = input_signal.astype(np.float32)

# Prepare Buffer (Size Len + 4 offset)
readBufferFloat = np.zeros(Len + 4, dtype=np.float32)
readBufferFloat[4:] = input_signal

readBufferLength = np.int32(Len)

# State variables
w_lpf1 = np.zeros(2, dtype=np.float32)
w_lpf2 = np.zeros(2, dtype=np.float32)
w_lpf3 = np.zeros(2, dtype=np.float32)

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
CAP_EXEC =  MALLOC_CAP_INTERNAL   # MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT **** MALLOC_CAP_INTERNAL 
CAP_DATA = MALLOC_CAP_INTERNAL

code_addr = session.device.allocate(code_size + 64, caps=CAP_EXEC, alignment=128)
args_addr = session.device.allocate(args_size, caps=CAP_DATA, alignment=128)

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

print(f"   Host Roundtrip Time: {(end_time - start_time)*1000:.2f} ms")

# Read Return Value (Cycles)
# The wrapper writes the return value to the last slot (index 31) of the args array
# Offset = 31 * 4 = 124 bytes
ret_bytes = session.device.read_memory(args_addr + 124, 4)
cycles = struct.unpack('<I', ret_bytes)[0]

# Calculate Time in us (Frequency = 360 MHz)
# Time (us) = Cycles / 360
time_us = cycles / 360.0

print(f"   Device Execution Cycles: {cycles}")
print(f"   Device Execution Time: {time_us:.4f} us")

# 6. Read Back Result
print("6. Reading back result...")
result_bytes = session.device.read_memory(addr_readBuffer, readBufferFloat.nbytes)
result_array = np.frombuffer(result_bytes, dtype=np.float32)
output_signal = result_array[4:]

# --- Python Implementation for Verification ---
def python_biquad(input_arr, coef, w):
    output_arr = np.zeros_like(input_arr)
    for i in range(len(input_arr)):
        d0 = input_arr[i] - coef[3] * w[0] - coef[4] * w[1]
        output_arr[i] = coef[0] * d0 + coef[1] * w[0] + coef[2] * w[1]
        w[1] = w[0]
        w[0] = d0
    return output_arr

# Run Python Simulation
print("   Running Python Simulation...")
py_buffer = readBufferFloat.copy()
py_signal = py_buffer[4:]

# Simulate 3 cascaded stages
w1_py = np.zeros(2, dtype=np.float32)
py_signal = python_biquad(py_signal, coeffs_lpf, w1_py)
w2_py = np.zeros(2, dtype=np.float32)
py_signal = python_biquad(py_signal, coeffs_lpf, w2_py)
w3_py = np.zeros(2, dtype=np.float32)
py_signal = python_biquad(py_signal, coeffs_lpf, w3_py)

expected_output = py_signal

# 7. Verification
print("7. Verifying Result...")
# Compare (ignore first few samples due to potential boundary effects if any, but here should be exact)
if np.allclose(output_signal, expected_output, atol=1e-4):
    print("SUCCESS: Device output matches Python simulation!")
else:
    print("FAILURE: Output mismatch!")
    diff = np.abs(output_signal - expected_output)
    print(f"   Max Diff: {np.max(diff)}")

# 8. Plotting
print("8. Generating Plot...")
plt.figure(figsize=(10, 8))

# Subplot 1: Input
plt.subplot(2, 1, 1)
plt.plot(t * 1000, input_signal, label='Input Signal', color='gray', alpha=0.7)
plt.title('Input Signal (1kHz + 10kHz)')
plt.xlabel('Time (ms)')
plt.ylabel('Amplitude')
plt.grid(True)
plt.legend()

# Subplot 2: Output Comparison
plt.subplot(2, 1, 2)
plt.plot(t * 1000, expected_output, label='Python Simulation (Expected)', color='blue', linestyle='-', linewidth=2, alpha=0.7)
plt.plot(t * 1000, output_signal, label='ESP32-P4 JIT (Device)', color='red', linestyle='--', linewidth=2)
plt.title('Output Signal Comparison (LPF @ 1kHz)')
plt.xlabel('Time (ms)')
plt.ylabel('Amplitude')
plt.grid(True)
plt.legend()

plt.tight_layout()
output_plot = os.path.join(os.path.dirname(__file__), 'biquad_plot.png')
plt.savefig(output_plot)
print(f"   Plot saved to: {output_plot}")

# 9. Cleanup
print("9. Cleaning up...")
session.device.free(code_addr)
session.device.free(args_addr)
session.device.free(addr_readBuffer)
session.device.free(addr_coeffs)
session.device.free(addr_w1)
session.device.free(addr_w2)
session.device.free(addr_w3)
session.device.disconnect()

final_bin.disassemble("asm.txt", False)
final_bin.print_memory_map()
final_bin.print_sections()
