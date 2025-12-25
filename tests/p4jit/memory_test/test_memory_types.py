import os
import sys
import numpy as np

# Add Host directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'host')))

from p4jit import P4JIT

def create_c_source():
    source_code = """
#include <stdint.h>

// Function: array_add_accumulate
// Adds all elements of the array and stores the result in arr[0]
// Returns the result as well.
int array_add_accumulate(int32_t *arr, int len) {
    int sum = 0;
    for (int i = 0; i < len; i++) {
        sum += arr[i];
    }
    
    // Store result in first position
    if (len > 0) {
        arr[0] = sum;
    }
    
    return sum;
}
"""
    source_dir = os.path.join(os.path.dirname(__file__), 'source')
    os.makedirs(source_dir, exist_ok=True)
    with open(os.path.join(source_dir, 'array_add.c'), 'w') as f:
        f.write(source_code)
    return os.path.join(source_dir, 'array_add.c')

def main():
    print("--- P4-JIT Memory Location Test ---")
    
    source_file = create_c_source()
    jit = P4JIT()
    
    expected_sum = 150
    
    # ---------------------------------------------------------
    # Test 1: Execution in PSRAM (External Memory)
    # ---------------------------------------------------------
    print("\n[TEST 1] Execution in PSRAM (External)")
    print("  Code Location: PSRAM")
    print("  Data Location: PSRAM")
    
    # 1. Prepare Data in PSRAM
    data_psram = np.array([10, 20, 30, 40, 50], dtype=np.int32)
    # Using P4JIT class constants
    data_psram = jit.set_p4_mem_location(data_psram, P4JIT.MALLOC_CAP_SPIRAM | P4JIT.MALLOC_CAP_8BIT)
    
    # 2. Load Function (Code in SPIRAM)
    func_psram = jit.load(
        source=source_file,
        function_name='array_add_accumulate',
        code_caps=P4JIT.MALLOC_CAP_SPIRAM | P4JIT.MALLOC_CAP_8BIT
    )
    
    # 3. Execute
    res_psram = func_psram(data_psram, np.int32(len(data_psram)))
    
    print(f"  Result: {res_psram} (Expected: {expected_sum})")
    print(f"  Modified Data[0]: {data_psram[0]}")
    
    if res_psram == expected_sum and data_psram[0] == expected_sum:
        print("  ✓ PSRAM Test Passed")
    else:
        print("  ✗ PSRAM Test Failed")
        
    func_psram.free()

    # ---------------------------------------------------------
    # Test 2: Execution in Internal SRAM (Fast Memory)
    # ---------------------------------------------------------
    print("\n[TEST 2] Execution in Internal SRAM")
    print("  Code Location: Internal SRAM (IRAM)")
    print("  Data Location: Internal SRAM (DMA Capable)")
    
    # 1. Prepare Data in Internal SRAM
    data_sram = np.array([10, 20, 30, 40, 50], dtype=np.int32)
    # Using P4JIT class constants
    data_sram = jit.set_p4_mem_location(data_sram, P4JIT.MALLOC_CAP_DMA | P4JIT.MALLOC_CAP_INTERNAL | P4JIT.MALLOC_CAP_8BIT)
    
    # 2. Load Function (Code in Internal RAM)
    func_sram = jit.load(
        source=source_file,
        function_name='array_add_accumulate',
        code_caps=P4JIT.MALLOC_CAP_INTERNAL | P4JIT.MALLOC_CAP_EXEC 
    )
    
    # 3. Execute
    res_sram = func_sram(data_sram, np.int32(len(data_sram)))
    
    print(f"  Result: {res_sram} (Expected: {expected_sum})")
    print(f"  Modified Data[0]: {data_sram[0]}")
    
    if res_sram == expected_sum and data_sram[0] == expected_sum:
        print("  ✓ SRAM Test Passed")
    else:
        print("  ✗ SRAM Test Failed")
        
    func_sram.free()
    
    jit.session.device.disconnect()
    print("\n--- Test Complete ---")

if __name__ == "__main__":
    main()
