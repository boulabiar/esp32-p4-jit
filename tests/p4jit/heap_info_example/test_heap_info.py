
import os
import sys
import numpy as np

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'host')))

from p4jit import P4JIT, MALLOC_CAP_SPIRAM, MALLOC_CAP_8BIT

def test_heap_info():
    print("--- P4JIT Heap Info Example ---")
    
    jit = P4JIT()
    
    # 1. Get Initial Stats
    jit.get_heap_stats(print_s=True)
    stats_initial = jit.get_heap_stats(print_s=False) # Capture for comparison
        
    # 2. Allocate Memory
    print("\n[Allocating 10KB SPIRAM...]")
    size = 1024 * 1024
    addr = jit.session.device.allocate(size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT, 16)
    print(f"  Allocated at 0x{addr:08X}")
    
    # 3. Get Post-Alloc Stats
    stats_post = jit.get_heap_stats(print_s=True)
        
    # Verify Sync
    diff = stats_initial['free_spiram'] - stats_post['free_spiram']
    print(f"\nFree SPIRAM decreased by: {diff} bytes")
    
    # Note: Exact match might not happen due to allocator overhead (metadata)
    if diff >= size:
         print("PASS: Free memory decreased as expected.")
    else:
         print(f"FAIL: Free memory did not decrease correctly. Diff={diff}, Alloc={size}")

    # 4. Cleanup
    jit.session.device.free(addr)
    print("\n[Freed Memory]")
    
    # 5. Final Stats
    stats_final = jit.get_heap_stats(print_s=True)
    
    if stats_final['free_spiram'] > stats_post['free_spiram']:
        print("PASS: Memory reclaimed.")
    else:
        print("FAIL: Memory not reclaimed.")

if __name__ == "__main__":
    test_heap_info()
