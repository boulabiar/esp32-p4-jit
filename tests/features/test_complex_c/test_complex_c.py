import sys
import os
import struct
import time
import numpy as np

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'host')))

from p4jit.toolchain import Builder
from p4jit.runtime import JITSession
from p4jit.runtime.memory_caps import *

print("--- P4-JIT Complex C Test (Multi-File) ---")

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
# data: int array
data = np.array([10, 20, 30, 40, 50], dtype=np.int32) 
length = np.int32(len(data))
scale = np.float32(1.5)
offset = np.float32(5.0)

print(f"   Data: {data}")
print(f"   Length: {length}")
print(f"   Scale: {scale}")
print(f"   Offset: {offset}")

# 3. Build JIT Function
print("3. Building JIT Function...")
builder = Builder()
source_dir = os.path.join(os.path.dirname(__file__), 'source')
main_source = os.path.join(source_dir, 'main.c')

# Pass 1: Probe
print("   Pass 1: Probing...")
# Builder will automatically discover math_utils.c and data_processor.c!
temp_bin = builder.wrapper.build_with_wrapper(
    source=main_source,
    function_name='complex_c_test',
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
    function_name='complex_c_test',
    base_address=code_addr,
    arg_address=args_addr
)

# Upload Code
print("   Uploading binary...")
# Load with Smart Args enabled!
remote_func = session.load_function(final_bin, args_addr, smart_args=True)

# 4. Execute
print("4. Executing complex_c_test...")

start_time = time.time()

# Call directly with NumPy args!
# complex_c_test(int *data, int len, float scale, float offset)
result = remote_func(data, length, scale, offset)
end_time = time.time()

print(f"   Result: {result} (Type: {type(result)})")
print(f"   Time: {(end_time - start_time)*1000:.2f} ms")

# 5. Verify
# Logic:
# for each val:
#   v = val * scale
#   v = v^2
#   v = v + offset
#   v = |v|
#   val = (int)v
# sum += val

# Manual calculation
expected_sum = 0
for val in [10, 20, 30, 40, 50]:
    v = float(val) * 1.5
    v = v * v
    v = v + 5.0
    v = abs(v)
    expected_sum += int(v)

expected_result = np.int32(expected_sum)

if result == expected_result:
    print(f"SUCCESS: Result is {result}")
else:
    print(f"FAILURE: Expected {expected_result}, got {result}")

# Cleanup
print("5. Cleaning up...")
session.device.free(code_addr)
session.device.free(args_addr)
session.device.disconnect()


final_bin.disassemble("asm.txt", False)










