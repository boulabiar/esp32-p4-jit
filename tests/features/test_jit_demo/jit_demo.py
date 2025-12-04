import sys
import os
import struct
import time

# Add project root to path to import p4_jit and esp32_loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'host')))

from p4jit.toolchain import Builder
from p4jit.runtime import JITSession
from p4jit.runtime.memory_caps import *


print("--- P4-JIT Demo ---")

# 1. Initialize Session & Find Device
print("1. Connecting to device...")
session = JITSession()
try:
    session.connect() # Auto-detects via PING
except Exception as e:
    print(f"Error connecting: {e}")
    # return # Don't return, let's see if we can debug more
    sys.exit() 

# 2. Pass 1: Probe Size
print("2. Pass 1: Probing binary size...")
builder = Builder()

# Source path relative to this script
source_file = os.path.join(os.path.dirname(__file__), 'source', 'compute.c')

# Compile with wrapper to get size (fake addresses)
temp_bin = builder.wrapper.build_with_wrapper(
    source=source_file,
    function_name='compute_sum',
    base_address=0x01003008,
    arg_address=0x03001008
)

code_size = temp_bin.total_size
# DEBUG: Print metadata keys
print(f"DEBUG: Metadata keys: {temp_bin.metadata.keys()}")
if 'addresses' in temp_bin.metadata:
    print(f"DEBUG: Addresses keys: {temp_bin.metadata['addresses'].keys()}")

args_size = temp_bin.metadata['addresses']['args_array_bytes']
print(f"   Code Size: {code_size} bytes")
print(f"   Args Size: {args_size} bytes")

# 3. Allocate Memory (Layer 2)
print("3. Allocating memory on device...")

# Use imported caps
# PSRAM is executable on P4, but we must request EXEC capability to ensure permissions
CAP_EXEC = MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT 
print(f"DEBUG: CAP_EXEC value: 0x{CAP_EXEC:08X}")
CAP_DATA = MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT

# Add padding (+64 bytes) because resolving large addresses (e.g. 0x48...) in the final pass
# requires more instructions/literal pool space than the placeholder (0x00...) used in Pass 1.
# Use 128-byte alignment for cache friendliness (P4 cache line size)
code_addr = session.device.allocate(code_size + 64, caps=CAP_EXEC, alignment=128)
args_addr = session.device.allocate(args_size, caps=CAP_DATA, alignment=128)

print(f"   Code Allocated at: 0x{code_addr:08X}")
print(f"   Args Allocated at: 0x{args_addr:08X}")

# 4. Pass 2: Final Build (Layer 1)
print("4. Pass 2: Final Compilation...")
final_bin = builder.wrapper.build_with_wrapper(
    source=source_file,
    function_name='compute_sum',
    base_address=code_addr,
    arg_address=args_addr
)

# 5. Upload & Create Handle (Layer 2)
print("5. Uploading binary...")
remote_func = session.load_function(final_bin, args_addr)

# 6. Execute
print("6. Executing compute_sum(10, 20)...")
# User manually packs arguments (int32, int32) -> bytes
# The wrapper expects an array of int32s.
# int a = args[0], int b = args[1]
args_data = struct.pack('<ii', 10, 20) 

start_time = time.time()
result = remote_func(args_data)
end_time = time.time()

# 7. Read Result
# The wrapper writes the result to the last slot (index 31) of the args array.
# We need to read this manually as CMD_EXEC returns the wrapper's status (0/ESP_OK).
result_addr = args_addr + (31 * 4)
result_bytes = session.device.read_memory(result_addr, 4)
result = struct.unpack('<f', result_bytes)[0]

print(f"   Result: {result}")
print(f"   Time: {(end_time - start_time)*1000:.2f} ms")

if result == 30:
    print("SUCCESS: 10 + 20 = 30")
else:
    print(f"FAILURE: Expected 30, got {result}")

# Cleanup
print("7. Cleaning up...")
session.device.free(code_addr)
session.device.free(args_addr)
session.device.disconnect()

