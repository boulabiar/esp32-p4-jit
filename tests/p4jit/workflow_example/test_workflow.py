"""
float apply_gain(uint8_t* data, int len, float gain) {
    for(int i=0; i<len; i++) {
        data[i] = (uint8_t)(data[i] * gain);
    }
    return gain;
}
"""

import numpy as np
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'host')))

from p4jit import P4JIT, MALLOC_CAP_SPIRAM, MALLOC_CAP_8BIT

def test_workflow():
    print("--- P4JIT Workflow Example ---")

    # 1. Setup (Auto-detect port)
    jit = P4JIT()

    # 2. Prepare Data
    # Create a large array to process
    input_data = np.random.randint(0, 100, 1024, dtype=np.uint8) # 0-100 to allow gain without instant clipping
    gain = np.float32(1.5)
    
    print(f"Input (first 5): {input_data[:5]}")

    # 3. Load Function (Full Control)
    # We explicitly set memory capabilities, even if they match defaults.
    # We use default alignment (16), default addresses, and default optimization (O3).
    source_path = os.path.join(os.path.dirname(__file__), "source", "audio_processing.c")
    
    func = jit.load(
        source=source_path, 
        function_name="apply_gain",
        code_caps=MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT,
        data_caps=MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT
    )

    # 4. Execute
    # The function modifies the data in-place or returns a result
    # We pass the array and the gain factor
    result = func(input_data, np.int32(len(input_data)), gain)

    print(f"Processing complete. Result: {result}")
    print(f"Output (first 5): {input_data[:5]}")

    # 5. Inspect Binary
    print(f"Total Size: {func.binary.total_size}")
    # print(f"Sections: {func.binary.sections}") # Sections might be large object
    # print(f"Functions: {func.binary.functions}")

    # Disassemble to file
    build_dir = os.path.join(os.path.dirname(__file__), "build")
    if not os.path.exists(build_dir):
        os.makedirs(build_dir)
        
    disasm_path = os.path.join(build_dir, "disassembly.txt")
    func.binary.disassemble(output=disasm_path, source_intermix=True)
    print(f"Disassembly saved to {disasm_path}")

    # Print details to stdout
    func.binary.print_sections()
    func.binary.print_symbols()
    func.binary.print_memory_map()

    # 6. Cleanup
    func.free()

if __name__ == "__main__":
    test_workflow()
