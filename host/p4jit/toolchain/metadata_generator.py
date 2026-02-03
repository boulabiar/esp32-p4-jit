import json
import os
from ..utils.logger import setup_logger, INFO_VERBOSE

logger = setup_logger(__name__)

# Types that require 64-bit (2 slots)
_64BIT_TYPES = {'int64_t', 'uint64_t', 'int64', 'uint64', 'double',
               'long long', 'unsigned long long', 'long long int',
               'unsigned long long int'}

def _is_64bit_type(type_str: str) -> bool:
    """Check if a type requires 64-bit (2 slots)."""
    clean_type = type_str.replace('const', '').replace('volatile', '').strip()
    return clean_type in _64BIT_TYPES

class MetadataGenerator:
    """
    Generate signature.json metadata file with function signature and memory addresses.
    """

    def __init__(self, signature_data, arg_address, base_address, args_array_size):
        self.signature = signature_data
        self.arg_address = arg_address
        self.base_address = base_address
        self.args_array_size = args_array_size

    def calculate_addresses(self):
        """Calculate memory addresses for arguments and return value, respecting 64-bit slot layout."""
        addresses = {
            'arguments': [],
            'return': {}
        }

        current_slot = 0
        for idx, param in enumerate(self.signature['parameters']):
            # Calculate slot count based on type
            if param['category'] == 'pointer':
                slot_count = 1  # Pointers are 32-bit on this platform
            elif _is_64bit_type(param['type']):
                slot_count = 2
            else:
                slot_count = 1

            addr = self.arg_address + (current_slot * 4)
            addresses['arguments'].append({
                'index': idx,
                'slot': current_slot,
                'slot_count': slot_count,
                'name': param['name'],
                'type': param['type'],
                'category': param['category'],
                'address': f"0x{addr:08x}"
            })
            current_slot += slot_count

        # Return value: check if 64-bit
        return_type = self.signature['return_type']
        return_slot_count = 2 if _is_64bit_type(return_type) else 1
        return_slot = self.args_array_size - return_slot_count
        return_addr = self.arg_address + (return_slot * 4)
        addresses['return'] = {
            'type': return_type,
            'slot': return_slot,
            'slot_count': return_slot_count,
            'address': f"0x{return_addr:08x}"
        }

        return addresses
    
    def generate_metadata(self):
        """Generate complete metadata dictionary."""
        addresses = self.calculate_addresses()
        
        metadata = {
            # Ensure compatibility with SmartArgs by including raw signature fields at top level
            'name': self.signature['name'],
            'return_type': self.signature['return_type'],
            'parameters': self.signature['parameters'],
            
            'function': {
                'name': self.signature['name'],
                'return_type': self.signature['return_type'],
                'wrapper_entry': 'call_remote'
            },
            'addresses': {
                'code_base': f"0x{self.base_address:08x}",
                'arg_base': f"0x{self.arg_address:08x}",
                'args_array_size': self.args_array_size,
                'args_array_bytes': self.args_array_size * 4
            },
            'arguments': addresses['arguments'],
            'result': addresses['return']
        }
        
        return metadata
    
    def save_json(self, output_dir):
        """
        Save metadata as JSON file in output directory.
        
        Args:
            output_dir: Directory to save signature.json
            
        Returns:
            str: Path to generated signature.json file
        """
        os.makedirs(output_dir, exist_ok=True)
        
        metadata = self.generate_metadata()
        
        output_path = os.path.join(output_dir, 'signature.json')
        
        logger.log(INFO_VERBOSE, f"Saving metadata to {output_path}")
        with open(output_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return output_path
