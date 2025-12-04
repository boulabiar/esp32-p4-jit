import sys
import os
import struct
import time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'host')))

from p4jit.toolchain import Builder
from p4jit.runtime import JITSession
from p4jit.runtime.memory_caps import *


print("--- P4-JIT Array Sum Test ---")

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
data = [10, 20, 30, 40, 50] # Sum = 150
# Pack as signed bytes (int8)
data_bytes = struct.pack(f'{len(data)}b', *data)
data_len = len(data)

# Allocate memory for the array in PSRAM (Data)
# MALLOC_CAP_8BIT is crucial for byte access
CAP_DATA = MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT

# Align to 128 bytes for cache safety
array_addr = session.device.allocate(len(data_bytes), caps=CAP_DATA, alignment=128)
print(f"   Array Allocated at: 0x{array_addr:08X}")

# Write data to device
session.device.write_memory(array_addr, data_bytes)
print(f"   Array Data Written: {data}")

# 3. Build JIT Function
print("3. Building JIT Function...")
builder = Builder()
source_file = os.path.join(os.path.dirname(__file__), 'source', 'sum_array.c')

# Pass 1: Probe
print("   Pass 1: Probing...")
temp_bin = builder.wrapper.build_with_wrapper(
    source=source_file,
    function_name='sum_array',
    base_address=0x03000004,
    arg_address=0x00030004
)

code_size = temp_bin.total_size
args_size = temp_bin.metadata['addresses']['args_array_bytes']

# Allocate Code & Args
# Must be executable
CAP_EXEC = MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT 

# Add padding (+64) and alignment (128)
code_addr = session.device.allocate(code_size + 64, caps=CAP_EXEC, alignment=128)
args_addr = session.device.allocate(args_size, caps=CAP_DATA, alignment=128)

print(f"   Code Allocated at: 0x{code_addr:08X}")
print(f"   Args Allocated at: 0x{args_addr:08X}")

# Pass 2: Final Build
print("   Pass 2: Final Compilation...")
final_bin = builder.wrapper.build_with_wrapper(
    source=source_file,
    function_name='sum_array',
    base_address=code_addr,
    arg_address=args_addr
)

# Upload Code
print("   Uploading binary...")
remote_func = session.load_function(final_bin, args_addr)

# 4. Execute
print("4. Executing sum_array(arr_ptr, len)...")
# Args: int8_t *arr (pointer is 32-bit int), int len
# Pack as: unsigned int (pointer), int (length)
args_data = struct.pack('<Ii', array_addr, data_len)

start_time = time.time()
remote_func(args_data)
end_time = time.time()

# 5. Read Result
# Result is at the last slot (index 31)
result_addr = args_addr + (31 * 4)
result_bytes = session.device.read_memory(result_addr, 4)
result = struct.unpack('<i', result_bytes)[0]

print(f"   Result: {result}")
print(f"   Time: {(end_time - start_time)*1000:.2f} ms")

expected_sum = sum(data)
if result == expected_sum:
    print(f"SUCCESS: Sum is {result}")
else:
    print(f"FAILURE: Expected {expected_sum}, got {result}")

# Cleanup
print("5. Cleaning up...")
session.device.free(array_addr)
session.device.free(code_addr)
session.device.free(args_addr)
session.device.disconnect()
