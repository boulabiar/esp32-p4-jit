
import os
import sys
import shutil
import numpy as np

# Add project root to path to ensure we can import p4jit
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'host')))

from p4jit import P4JIT 

# ==========================================
# Step 1: Define C Code
# ==========================================
C_CODE = r"""
#include <stdint.h>

/**
 * Doubles every element in the array and returns the sum of the doubled values.
 * 
 * @param array Pointer to the array of integers
 * @param length Number of elements in the array
 * @return Sum of all elements after doubling
 */
int double_and_sum(int* array, int length) {
    int sum = 0;
    for (int i = 0; i < length; i++) {
        array[i] = array[i] * 2;
        sum += array[i];
    }
    return sum;
}
"""

def test_array_double_and_sum_smart():
    print("--- P4JIT Array Double & Sum Example (Smart Args) ---")

    # ==========================================
    # Step 2: Write C Code to File
    # ==========================================
    current_dir = os.path.dirname(os.path.abspath(__file__))
    source_dir = os.path.join(current_dir, "source")
    
    if not os.path.exists(source_dir):
        os.makedirs(source_dir)
        
    source_file_path = os.path.join(source_dir, "array_ops.c")
    
    with open(source_file_path, "w") as f:
        f.write(C_CODE)
        
    print(f"Created C source file at: {source_file_path}")

    # ==========================================
    # Step 3: Initialize P4JIT & Load Function
    # ==========================================
    jit = P4JIT()
    
    # Load the function (smart_args=True is default)
    func = jit.load(
        source=source_file_path,
        function_name="double_and_sum"
    )
    
    # ==========================================
    # Step 4: Prepare Data (NumPy)
    # ==========================================
    # 1. Create standard NumPy array (int32)
    np_array = np.array([1, 2, 3, 4, 5], dtype=np.int32)
    
    # 2. Mark it for P4 Memory (SRAM/SPIRAM)
    # This tells the Smart Args system to allocate this in the specified memory region
    # Use P4JIT attributes for memory capabilities
    p4_array = jit.set_p4_mem_location(np_array, P4JIT.MALLOC_CAP_SPIRAM | P4JIT.MALLOC_CAP_8BIT)
    
    print(f"Prepared P4 Array: {p4_array} (Caps: {p4_array.p4_caps})")

    # ==========================================
    # Step 5: Execute Function
    # ==========================================
    
    # Calculate Expected Results BEFORE execution (since array is modified in-place)
    expected_sum = sum([x * 2 for x in np_array])
    expected_values = np.array([x * 2 for x in np_array], dtype=np.int32)
    
    # We pass the arguments naturally.
    # P4JIT will handle allocation, copying, and pointer passing.
    print(f"Executing 'double_and_sum' on {np_array}...")
    
    length = np.int32(len(p4_array))
    
    # Call the JIT function
    # Returns the actual C return value directly
    result_sum = func(p4_array, length)
    
    # ==========================================
    # Step 6: Verify Results
    # ==========================================
    
    print(f"Returned Sum: {result_sum} (Expected: {expected_sum})")
    
    # Check if the array was updated in place (Requires func.sync_arrays = True)
    print(f"Modified Array (Host View): {p4_array}")
    
    # Assertions
    assert result_sum == expected_sum, f"Sum mismatch: Got {result_sum}, Expected {expected_sum}"
    np.testing.assert_array_equal(p4_array, expected_values, err_msg="Array content mismatch")
    
    print("SUCCESS: Test passed!")
    
    # Cleanup (Optional, P4JIT session end handles most, but good practice)
    func.free()

if __name__ == "__main__":
    test_array_double_and_sum_smart()
