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

print("--- P4-JIT Smart Args Test ---")

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
# Create NumPy array
data = np.array([10, 20, 30, 40, 50], dtype=np.int32) # Sum = 150
length = np.int32(len(data))
scale = np.float32(2.0)

print(f"   Data: {data}")
print(f"   Length: {length}")
print(f"   Scale: {scale}")

# 3. Build JIT Function
print("3. Building JIT Function...")
builder = Builder()
source_file = os.path.join(os.path.dirname(__file__), 'source', 'smart_test.c')

# Pass 1: Probe
print("   Pass 1: Probing...")
temp_bin = builder.wrapper.build_with_wrapper(
    source=source_file,
    function_name='smart_test',
    base_address=0x03000004,
    arg_address=0x00030004
)

code_size = temp_bin.total_size
args_size = temp_bin.metadata['addresses']['args_array_bytes']

# Allocate Code & Args
# Must be executable
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
    source=source_file,
    function_name='smart_test',
    base_address=code_addr,
    arg_address=args_addr
)

# Upload Code
print("   Uploading binary...")
# Load with Smart Args enabled!
remote_func = session.load_function(final_bin, args_addr, smart_args=True)

# 4. Execute
print("4. Executing smart_test(arr, len, scale)...")

start_time = time.time()
# Call directly with NumPy args!
# smart_test(int *arr, int len, float scale)
result = remote_func(data, length, scale)
end_time = time.time()

print(f"   Result: {result} (Type: {type(result)})")
print(f"   Time: {(end_time - start_time)*1000:.2f} ms")

# 5. Verify
expected_sum = np.sum(data)
expected_result = int(expected_sum * scale)

if result == expected_result:
    print(f"SUCCESS: Result is {result}")
else:
    print(f"FAILURE: Expected {expected_result}, got {result}")

# Cleanup
print("5. Cleaning up...")
session.device.free(code_addr)
session.device.free(args_addr)
session.device.disconnect()
