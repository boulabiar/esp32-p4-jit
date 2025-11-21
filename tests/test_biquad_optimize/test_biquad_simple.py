import sys
import os
import struct
import time
import numpy as np

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from esp32_loader import Builder
from p4_jit import JITSession
from p4_jit.memory_caps import *

print("--- P4-JIT Biquad Filter Test ---")

# 1. Connect
print("1. Connecting to device...")
session = JITSession()
try:
    session.connect()
except Exception as e:
    print(f"Error connecting: {e}")
    sys.exit()

# 2. Prepare Data (Strict NumPy Types)
print("2. Preparing Data...")

# readBufferFloat (36 floats)
readBufferFloat = np.array([
    0.0, 0.0, 0.0, 0.0,
    1.0, 0.5, -0.3, -0.8, -0.5, 0.2, 0.9, 0.7,
    0.0, -0.6, -0.9, -0.4, 0.4, 0.8, 0.6, -0.1,
    -0.7, -0.8, -0.2, 0.5, 0.9, 0.5, -0.2, -0.7,
    -0.6, 0.1, 0.8, 0.7, 0.1, -0.5, -0.8, -0.3
], dtype=np.float32)

readBufferLength = np.int32(32)

coeffs_lpf = np.array([
    0.0674553,
    0.1349106,
    0.0674553,
    -1.1429806,
    0.4128018
], dtype=np.float32)

w_lpf1 = np.array([0.0, 0.0], dtype=np.float32)
w_lpf2 = np.array([0.0, 0.0], dtype=np.float32)
w_lpf3 = np.array([0.0, 0.0], dtype=np.float32)

print(f"   Buffer Length: {len(readBufferFloat)}")

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

# Add padding (+64) and alignment (128)
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
# Load WITHOUT Smart Args to allow manual memory management
remote_func = session.load_function(final_bin, args_addr, smart_args=False)

# 4. Manual Memory Allocation for Arrays
print("4. Allocating Device Memory for Arrays...")

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

print(f"   readBuffer: 0x{addr_readBuffer:08X}")

# 5. Execute
print("5. Executing process_audio...")

# Pack arguments manually:
# process_audio(float *readBufferFloat, int readBufferLength, float *coeffs_lpf, float *w_lpf1, float *w_lpf2, float *w_lpf3)
# Pointers are passed as 32-bit integers (uint32)
# Length is int32
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

# 6. Read Back Result
print("6. Reading back result...")
# Read back the modified readBufferFloat
result_bytes = session.device.read_memory(addr_readBuffer, readBufferFloat.nbytes)
result_array = np.frombuffer(result_bytes, dtype=np.float32)

print("   Original Buffer (First 10):", readBufferFloat[:10])
print("   Modified Buffer (First 10):", result_array[:10])

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



