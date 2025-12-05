"""
Example: Bidirectional Data Sync (Automatic In-Place Array Updates)

This example demonstrates the automatic sync-back feature of Smart Args.
1. sync_arrays=True (Default): Arrays modified on device are updated on host.
2. sync_arrays=False: Arrays are NOT updated on host.
"""

import numpy as np
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'host')))

from p4jit import P4JIT

def test_bidirectional():
    print("--- P4JIT Bidirectional Sync Example ---")
    
    # 1. Setup
    jit = P4JIT()
    
    source_path = os.path.join(os.path.dirname(__file__), 'source', 'bidirectional.c')
    
    # ---------------------------------------------------------
    # Test 1: Default Behavior (Sync Enabled)
    # ---------------------------------------------------------
    print("\n[Test 1] Testing Default Sync (True)...")
    
    # 1. Load function (Defaults to sync_arrays=True)
    func = jit.load(source_path, "modify_array")
    
    # Verify default config
    if func.sync_arrays != True:
        print("FAIL: Default sync_arrays should be True")
        return
        
    # Prepare Data
    data = np.array([1, 2, 3, 4], dtype=np.int32)
    expected = data * 2
    
    print(f"  Input: {data}")
    
    # Execute
    # The function now returns the first element of the modified array
    ret_val = func(data, np.int32(len(data)))
    
    print(f"  Output: {data}")
    print(f"  Return Value: {ret_val}")
    
    # Verify Data Sync
    if np.array_equal(data, expected):
        print("PASS: Data was updated in-place.")
    else:
        print(f"FAIL: Data was NOT updated. Expected {expected}, got {data}")
        return

    # Verify Return Value (Should be first element of modified array: 1 * 2 = 2)
    if ret_val == expected[0]:
        print(f"PASS: Return value correct ({ret_val}).")
    else:
        print(f"FAIL: Return value incorrect. Expected {expected[0]}, got {ret_val}")
        return

    # ---------------------------------------------------------
    # Test 2: Disable Sync
    # ---------------------------------------------------------
    print("\n[Test 2] Testing Disabled Sync (False)...")
    
    # Disable global sync for this function
    func.sync_arrays = False
    
    if func.sync_arrays != False:
         print("FAIL: Failed to set sync_arrays to False")
         return
         
    # Prepare fresh data
    data_nose = np.array([10, 20, 30, 40], dtype=np.int32)
    original = data_nose.copy()
    
    print(f"  Input: {data_nose}")
    
    # Execute
    func(data_nose, np.int32(len(data_nose)))
    
    print(f"  Output: {data_nose}")
    
    # Verify (Should match original)
    if np.array_equal(data_nose, original):
        print("PASS: Data was NOT updated (as expected).")
    else:
        print(f"FAIL: Data WAS updated but sync was disabled! Got {data_nose}")
        return
        
    print("\n--- All Tests Passed ---")

if __name__ == "__main__":
    test_bidirectional()
