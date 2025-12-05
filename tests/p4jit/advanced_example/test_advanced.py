"""
typedef struct {
    float x;
    int y;
} Point;

float sum_point(Point* p, int8_t z, uint16_t* arr) {
    return p->x + (float)p->y + (float)z + (float)arr[0];
}

/*
IMPORTANT:
If your entry point function uses custom typedefs (like Point above), 
you MUST add them to config/std_types.h.
The wrapper generator copies std_types.h to the build directory and includes it,
so the compiler needs to see your custom types there.
*/
"""

import struct
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'host')))

from p4jit import P4JIT, MALLOC_CAP_SPIRAM, MALLOC_CAP_8BIT


def test_advanced():
    print("--- P4JIT Advanced Example (Manual Struct) ---")

    jit = P4JIT()
    
    # Loads from source/geometry.c
    source_path = os.path.join(os.path.dirname(__file__), "source", "geometry.c")
    
    func = jit.load(
        source=source_path,
        function_name="sum_point",
        smart_args=False
    )

    device = jit.session.device

    # 2. Prepare Struct Data (Point* p)
    # struct Point { float x; int y; };
    # We pack x=10.5 (float), y=20 (int)
    struct_data = struct.pack("<fi", 10.5, 20)
    struct_addr = device.allocate(len(struct_data), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT, alignment=16)
    device.write_memory(struct_addr, struct_data)
    print(f"Struct allocated at 0x{struct_addr:08X}")

    # 3. Prepare Array Data (uint16_t* arr)
    # We create an array of one element: [100]
    arr_data = struct.pack("<H", 100)
    arr_addr = device.allocate(len(arr_data), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT, alignment=16)
    device.write_memory(arr_addr, arr_data)
    print(f"Array allocated at 0x{arr_addr:08X}")

    # 4. Prepare Scalar Data (int8_t z)
    z_val = -5

    # 5. Execute
    # Since smart_args=False, we must manually pack the arguments for the wrapper.
    # The wrapper expects a buffer of 32-bit slots.
    # Function: sum_point(Point* p, int8_t z, uint16_t* arr)
    # Arg 0: p (Pointer) -> Pack as 32-bit address
    # Arg 1: z (int8_t)  -> Pack as 32-bit integer (Sign-extended)
    # Arg 2: arr (Pointer)-> Pack as 32-bit address

    args_blob = struct.pack("<IiI", struct_addr, z_val, arr_addr)

    # Call the function with the raw args blob
    # NOTE: When using the wrapper (jit.load), the return value is the STATUS (0=OK).
    # The actual function result is written to the last slot of the args buffer (Index 31).
    status = func(args_blob)
    if status != 0:
        print(f"Execution failed with status: {status}")

    # 6. Read & Unpack Result
    # The result is at args_addr + (31 * 4) = args_addr + 124
    result_addr = func.args_addr + 124
    raw_result_bytes = device.read_memory(result_addr, 4)

    # Unpack bytes as float ('f')
    result = struct.unpack("<f", raw_result_bytes)[0]

    print(f"Struct Sum: {result}") # Should be 10.5 + 20 + (-5) + 100 = 125.5
    
    expected = 10.5 + 20 + (-5) + 100
    if abs(result - expected) < 0.001:
        print("SUCCESS: Result matches expected value")
    else:
        print(f"FAILURE: Expected {expected}, got {result}")

    # 7. Cleanup
    device.free(struct_addr) # Free the struct memory
    device.free(arr_addr)    # Free the array memory
    func.free()              # Free the function code & args buffer

if __name__ == "__main__":
    test_advanced()
