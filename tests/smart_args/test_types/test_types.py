import sys
import os
import numpy as np

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'host')))

from p4jit.toolchain import Builder
from p4jit.runtime import JITSession

def test_types():
    print("--- P4-JIT Smart Args Types Test ---")

    # 1. Connect
    print("1. Connecting to device...")
    session = JITSession()
    try:
        session.connect()
    except Exception as e:
        print(f"Error connecting: {e}")
        sys.exit(1)

    # 2. Prepare Data with Specific NumPy Types
    print("2. Preparing Data...")
    
    # Scalars
    val_a = np.int8(-10)
    val_b = np.uint8(200)
    val_c = np.int16(-3000)
    val_d = np.uint16(60000)
    val_e = np.int32(100000)
    val_f = np.float32(123.456)
    
    # Array
    array_data = np.array([1, 2, 3, 4, 5], dtype=np.int32)
    val_len = np.int32(len(array_data))
    
    print(f"   a (int8): {val_a}")
    print(f"   b (uint8): {val_b}")
    print(f"   c (int16): {val_c}")
    print(f"   d (uint16): {val_d}")
    print(f"   e (int32): {val_e}")
    print(f"   f (float): {val_f}")
    print(f"   array: {array_data}")
    
    # 3. Build
    print("3. Building...")
    builder = Builder()
    source_file = os.path.join(os.path.dirname(__file__), 'source', 'types_test.c')
    
    # Pass 1: Probe
    temp_bin = builder.wrapper.build_with_wrapper(
        source=source_file,
        function_name='test_all_types',
        base_address=0x03000004,
        arg_address=0x00030004
    )
    
    # Allocate
    code_addr = session.device.allocate(temp_bin.total_size + 64, caps=1, alignment=16) # Exec
    args_addr = session.device.allocate(temp_bin.metadata['addresses']['args_array_bytes'], caps=2, alignment=16) # Data
    
    # Pass 2: Final
    final_bin = builder.wrapper.build_with_wrapper(
        source=source_file,
        function_name='test_all_types',
        base_address=code_addr,
        arg_address=args_addr
    )
    
    # 4. Upload & Load
    print("4. Uploading...")
    remote_func = session.load_function(final_bin, args_addr, smart_args=True)
    
    # 5. Execute
    print("5. Executing...")
    # Pass arguments directly!
    result = remote_func(val_a, val_b, val_c, val_d, val_e, val_f, array_data, val_len)
    
    print(f"   Result: {result}")
    
    # 6. Verify
    expected_sum = int(val_a) + int(val_b) + int(val_c) + int(val_d) + int(val_e) + int(val_f) + np.sum(array_data)
    expected_sum = np.int32(expected_sum) # Simulate C int32 overflow/wrap behavior if any
    
    print(f"   Expected: {expected_sum}")
    
    if result == expected_sum:
        print("SUCCESS: Result matches expected sum!")
    else:
        print(f"FAILURE: Expected {expected_sum}, got {result}")

    # Cleanup
    session.device.free(code_addr)
    session.device.free(args_addr)
    session.device.disconnect()

if __name__ == "__main__":
    test_types()
