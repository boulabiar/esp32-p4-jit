import struct
import numpy as np
import yaml
import os
from typing import Any, List, Dict, Optional
from .memory_caps import MALLOC_CAP_SPIRAM, MALLOC_CAP_8BIT

class SmartArgs:
    """
    Handles automatic argument processing for remote functions.
    - Converts NumPy arrays to device memory allocations.
    - Packs arguments into binary blob.
    - Reads and converts return values.
    - Manages memory cleanup.
    """
    
    def __init__(self, device_manager, signature: Dict[str, Any]):
        self.dm = device_manager
        self.signature = signature
        self.allocations: List[int] = []
        self._load_config()
        
    def _load_config(self):
        """Load NumPy type mapping configuration."""
        # Assuming config is at ../config/numpy_types.yaml relative to this file
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, 'config', 'numpy_types.yaml')
        
        with open(config_path, 'r') as f:
            self.type_map = yaml.safe_load(f)['type_map']
            
        # Reverse map for return value conversion (C type -> NumPy dtype)
        self.reverse_type_map = {v: k for k, v in self.type_map.items()}
        
        # Add standard C types aliases
        self.reverse_type_map['int'] = 'int32'
        self.reverse_type_map['signed int'] = 'int32'
        self.reverse_type_map['unsigned int'] = 'uint32'
        self.reverse_type_map['short'] = 'int16'
        self.reverse_type_map['unsigned short'] = 'uint16'
        self.reverse_type_map['long'] = 'int32'
        self.reverse_type_map['unsigned long'] = 'uint32'
        self.reverse_type_map['char'] = 'int8'
        self.reverse_type_map['unsigned char'] = 'uint8'

    def pack(self, *args) -> bytes:
        """
        Process arguments and pack them into a binary blob.
        Allocates memory for arrays and pointers.
        """
        parameters = self.signature['parameters']
        
        if len(args) != len(parameters):
            raise ValueError(f"Expected {len(parameters)} arguments, got {len(args)}")
            
        packed_args = []
        
        for i, (arg, param) in enumerate(zip(args, parameters)):
            param_type = param['type']
            category = param['category']
            
            if category == 'pointer':
                packed_val = self._handle_pointer(arg, param_type)
                packed_args.append(packed_val)
            else:
                packed_val = self._handle_value(arg, param_type)
                packed_args.append(packed_val)
                
        # Pack all arguments into the args buffer
        # The wrapper expects arguments at 4-byte aligned slots
        # We pack them as 32-bit values (pointers or values)
        # Note: This assumes all args fit in 32-bit slots (int, float, pointers)
        # Double would need special handling if we supported 64-bit args fully
        
        buffer = b''
        for val in packed_args:
            buffer += val
            
        return buffer

    def _handle_pointer(self, arg: Any, param_type: str) -> bytes:
        """Handle pointer arguments (NumPy arrays)."""
        if not isinstance(arg, np.ndarray):
            raise TypeError(f"Expected NumPy array for pointer argument (type {param_type}), got {type(arg)}")
            
        # Check dtype match
        # We need to map C type (e.g. 'int *') to expected numpy dtype
        # Simple heuristic: remove '*' and whitespace
        base_c_type = param_type.replace('*', '').strip()
        
        # If it's void*, we accept any type, otherwise check match
        if base_c_type != 'void':
            expected_dtype_str = self.reverse_type_map.get(base_c_type)
            if expected_dtype_str:
                expected_dtype = np.dtype(expected_dtype_str)
                if arg.dtype != expected_dtype:
                     # Allow safe casting if needed, or raise error
                     # For now, strict check to prevent surprises
                     if arg.dtype.itemsize != expected_dtype.itemsize:
                         raise TypeError(f"Array dtype mismatch: expected {expected_dtype}, got {arg.dtype}")
        
        # Flatten array to ensure contiguous memory
        flat_arr = arg.ravel()
        
        # Allocate memory on device
        size_bytes = flat_arr.nbytes
        # Use SPIRAM for data by default
        addr = self.dm.allocate(size_bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT, 16)
        self.allocations.append(addr)
        
        # Write data
        self.dm.write_memory(addr, flat_arr.tobytes())
        
        # Return address as 32-bit integer
        return struct.pack('<I', addr)

    def _handle_value(self, arg: Any, param_type: str) -> bytes:
        """Handle scalar value arguments."""
        # Enforce NumPy types
        if not isinstance(arg, (np.generic, np.ndarray)):
            raise TypeError(f"Smart Args requires NumPy types for all arguments. Got {type(arg)} for param type {param_type}. Please use np.int32(), np.float32(), etc.")

        if 'float' in param_type:
            return struct.pack('<f', float(arg))
        elif 'double' in param_type:
            # Wrapper truncates to float (32-bit)
            return struct.pack('<f', float(arg))
        else:
            # Integers (signed/unsigned)
            # We pack as 32-bit int. The wrapper handles casting.
            return struct.pack('<i', int(arg))

    def get_return_value(self, args_addr: int) -> Any:
        """
        Read and convert return value from the last slot of args array.
        """
        return_type = self.signature['return_type']
        
        if return_type == 'void':
            return None
            
        # Read the last slot (index 31)
        # Args array size is typically 32 slots (128 bytes)
        # Return value is at offset 124 (31 * 4)
        # TODO: Get args_array_size from config if possible, currently hardcoded to match default
        return_offset = 124 
        raw_bytes = self.dm.read_memory(args_addr + return_offset, 4)
        
        if '*' in return_type:
            # Pointer -> return address (uint32)
            val = struct.unpack('<I', raw_bytes)[0]
            return np.uint32(val)
            
        elif 'float' in return_type or 'double' in return_type:
            # Float/Double -> return float32
            val = struct.unpack('<f', raw_bytes)[0]
            return np.float32(val)
            
        else:
            # Integers
            # The wrapper cast the result to the specific type pointer
            # e.g. *(int8_t*)&io[31] = result
            # We read 4 bytes. The lower byte(s) contain the value.
            # We need to interpret these bytes as the correct type.
            
            val_i32 = struct.unpack('<i', raw_bytes)[0]
            
            if return_type in self.reverse_type_map:
                dtype_str = self.reverse_type_map[return_type]
                # Use numpy to cast the value to the correct type
                # This handles overflow/wrapping correctly for the target type
                return np.dtype(dtype_str).type(val_i32)
            else:
                # Fallback for unknown types (e.g. size_t, etc.) -> return as int
                return val_i32

    def cleanup(self):
        """Free all allocated memory."""
        for addr in self.allocations:
            try:
                self.dm.free(addr)
            except Exception as e:
                print(f"Warning: Failed to free memory at 0x{addr:08x}: {e}")
        self.allocations.clear()
