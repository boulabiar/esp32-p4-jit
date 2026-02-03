import struct
import numpy as np
import yaml
import os
from typing import Any, List, Dict, Optional
from .memory_caps import MALLOC_CAP_SPIRAM, MALLOC_CAP_8BIT
from ..utils.logger import setup_logger, INFO_VERBOSE

logger = setup_logger(__name__)

class SmartArgs:
    """
    Handles automatic argument processing for remote functions.
    - Converts NumPy arrays to device memory allocations.
    - Packs arguments into binary blob (supports 64-bit types).
    - Reads and converts return values.
    - Manages memory cleanup.
    - Handles automatic sync-back of arrays if enabled.
    """

    # Types that require 64-bit (2 slots / 8 bytes)
    _64BIT_TYPES = {'int64_t', 'uint64_t', 'int64', 'uint64', 'double',
                   'long long', 'unsigned long long', 'long long int',
                   'unsigned long long int'}

    def __init__(self, device_manager, signature: Dict[str, Any], sync_enabled: bool = True):
        self.dm = device_manager
        self.signature = signature
        # Configuration
        self.sync_enabled = sync_enabled
        
        # State
        self.allocations: List[int] = []
        self.tracked_arrays: List[Dict[str, Any]] = []
        self._load_config()
        
    def _load_config(self):
        """Load NumPy type mapping configuration."""
        # Assuming config is at ../../../config/numpy_types.yaml relative to this file
        # host/p4jit/runtime/smart_args.py -> ../../../
        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
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
            # 64-bit types
            self.reverse_type_map['long long'] = 'int64'
            self.reverse_type_map['long long int'] = 'int64'
            self.reverse_type_map['unsigned long long'] = 'uint64'
            self.reverse_type_map['unsigned long long int'] = 'uint64'
            self.reverse_type_map['int64_t'] = 'int64'
            self.reverse_type_map['uint64_t'] = 'uint64'
        except Exception as e:
            logger.error(f"Failed to load numpy type config: {e}")
            raise e

    def pack(self, *args) -> bytes:
        """
        Process arguments and pack them into a binary blob.
        Allocates memory for arrays and pointers.
        """
        parameters = self.signature['parameters']
        
        if len(args) != len(parameters):
            logger.error(f"Argument mismatch: Expected {len(parameters)}, got {len(args)}")
            raise ValueError(f"Expected {len(parameters)} arguments, got {len(args)}")
            
        packed_args = []
        
        for i, (arg, param) in enumerate(zip(args, parameters)):
            param_type = param['type']
            category = param['category']
            
            logger.log(INFO_VERBOSE, f"Processing Arg {i} ({param['name']}): Type={param_type}, Cat={category}")
            
            if category == 'pointer':
                packed_val = self._handle_pointer(arg, param_type)
                packed_args.append(packed_val)
            else:
                packed_val = self._handle_value(arg, param_type)
                packed_args.append(packed_val)
                
        # Pack all arguments into the args buffer
        # The wrapper expects arguments at 4-byte aligned slots
        buffer = b''
        for val in packed_args:
            buffer += val
            
        return buffer

    def _handle_pointer(self, arg: Any, param_type: str) -> bytes:
        """Handle pointer arguments (NumPy arrays)."""
        if not isinstance(arg, np.ndarray):
            logger.error(f"Type Mismatch: Expected NumPy array for {param_type}, got {type(arg)}")
            raise TypeError(f"Expected NumPy array for pointer argument (type {param_type}), got {type(arg)}")
            
        # Check dtype match
        base_c_type = param_type.replace('*', '').strip()
        
        # If it's void*, we accept any type, otherwise check match
        if base_c_type != 'void':
            expected_dtype_str = self.reverse_type_map.get(base_c_type)
            if expected_dtype_str:
                expected_dtype = np.dtype(expected_dtype_str)
                if arg.dtype != expected_dtype:
                     if arg.dtype.itemsize != expected_dtype.itemsize:
                         logger.error(f"Dtype Mismatch: Expected {expected_dtype}, got {arg.dtype}")
                         raise TypeError(f"Array dtype mismatch: expected {expected_dtype}, got {arg.dtype}")
        
        # Flatten array to ensure contiguous memory
        flat_arr = arg.ravel()

        # Allocate memory on device
        size_bytes = flat_arr.nbytes

        # Check for .p4_caps attribute, otherwise use default SPIRAM
        if hasattr(arg, 'p4_caps'):
            caps = arg.p4_caps
            logger.log(INFO_VERBOSE, f"Allocating array buffer: {size_bytes} bytes (caps=0x{caps:X} from .p4_caps)")
        else:
            caps = MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT
            logger.log(INFO_VERBOSE, f"Allocating array buffer: {size_bytes} bytes (default SPIRAM)")

        addr = self.dm.allocate(size_bytes, caps, 16)
        self.allocations.append(addr)
        
        # Write data
        self.dm.write_memory(addr, flat_arr.tobytes())
        
        # Track for Sync-Back (if enabled)
        if self.sync_enabled:
             self.tracked_arrays.append({
                 'addr': addr,
                 'array': arg,           # Reference to original array
                 'size': size_bytes,     # Size in bytes
                 'shape': arg.shape,     # Original shape
                 'dtype': arg.dtype      # Original dtype
             })
        
        # Return address as 32-bit integer
        return struct.pack('<I', addr)

    def _is_64bit_type(self, type_str: str) -> bool:
        """Check if a type requires 64-bit (2 slots)."""
        clean_type = type_str.replace('const', '').replace('volatile', '').strip()
        return clean_type in self._64BIT_TYPES

    def _handle_value(self, arg: Any, param_type: str) -> bytes:
        """Handle scalar value arguments."""
        # Enforce NumPy types
        if not isinstance(arg, (np.generic, np.ndarray)):
            logger.warning(f"Using standard python types ({type(arg)}) is deprecated. Please use np.int32, np.float32 etc.")

        # Handle 64-bit types (use 2 slots / 8 bytes)
        if self._is_64bit_type(param_type):
            if 'double' in param_type:
                # Double: pack as 64-bit float (little-endian)
                return struct.pack('<d', float(arg))
            elif 'unsigned' in param_type or 'uint' in param_type:
                # Unsigned 64-bit integer
                return struct.pack('<Q', int(arg) & 0xFFFFFFFFFFFFFFFF)
            else:
                # Signed 64-bit integer
                return struct.pack('<q', int(arg))

        # 32-bit types (1 slot / 4 bytes)
        if 'float' in param_type:
            return struct.pack('<f', float(arg))
        else:
            # Integers (signed/unsigned) - 32-bit
            return struct.pack('<i', int(arg))

    def get_return_value(self, args_addr: int) -> Any:
        """
        Read and convert return value from the args array.
        64-bit types use 2 consecutive slots.
        """
        return_type = self.signature['return_type']

        if return_type == 'void':
            return None

        # Determine if 64-bit return type
        is_64bit = self._is_64bit_type(return_type)

        # Calculate return offset
        # Default args array is 32 slots (128 bytes)
        # 64-bit uses slots 30-31, 32-bit uses slot 31
        if is_64bit:
            return_offset = 30 * 4  # 120 bytes
            raw_bytes = self.dm.read_memory(args_addr + return_offset, 8)
        else:
            return_offset = 31 * 4  # 124 bytes
            raw_bytes = self.dm.read_memory(args_addr + return_offset, 4)

        if '*' in return_type:
            # Pointer -> return address (uint32)
            val = struct.unpack('<I', raw_bytes)[0]
            return np.uint32(val)

        elif is_64bit:
            # 64-bit types
            if 'double' in return_type:
                val = struct.unpack('<d', raw_bytes)[0]
                return np.float64(val)
            elif 'unsigned' in return_type or 'uint' in return_type:
                val = struct.unpack('<Q', raw_bytes)[0]
                return np.uint64(val)
            else:
                val = struct.unpack('<q', raw_bytes)[0]
                return np.int64(val)

        elif 'float' in return_type:
            val = struct.unpack('<f', raw_bytes)[0]
            return np.float32(val)

        else:
            # 32-bit integers
            val_i32 = struct.unpack('<i', raw_bytes)[0]

            if return_type in self.reverse_type_map:
                dtype_str = self.reverse_type_map[return_type]
                return np.dtype(dtype_str).type(val_i32)
            else:
                return val_i32

    def sync_back(self):
        """
        Reads memory from device and updates host arrays in-place.
        """
        if not self.sync_enabled or not self.tracked_arrays:
            return

        for item in self.tracked_arrays:
            try:
                # 1. Read modified data
                logger.log(INFO_VERBOSE, f"Syncing back array from 0x{item['addr']:08X}")
                raw_bytes = self.dm.read_memory(item['addr'], item['size'])
                
                # 2. Create a view of the new data with correct type/shape
                new_data = np.frombuffer(raw_bytes, dtype=item['dtype']).reshape(item['shape'])
                
                # 3. Update original array in-place
                np.copyto(item['array'], new_data)
            except Exception as e:
                logger.warning(f"Failed to sync back memory at 0x{item['addr']:08x}: {e}")

    def cleanup(self):
        """Free all allocated memory."""
        logger.log(INFO_VERBOSE, f"Cleaning up {len(self.allocations)} temporary allocations")
        for addr in self.allocations:
            try:
                self.dm.free(addr)
            except Exception as e:
                logger.warning(f"Failed to free memory at 0x{addr:08x}: {e}")
        
        # Clear all state
        self.allocations.clear()
        self.tracked_arrays.clear()
