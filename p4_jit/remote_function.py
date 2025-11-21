import struct
from typing import Any

class RemoteFunction:
    """
    Represents a function loaded on the remote device.
    """
    def __init__(self, device_manager, code_addr: int, args_addr: int):
        self.dm = device_manager
        self.code_addr = code_addr
        self.args_addr = args_addr

    def __call__(self, args_blob: bytes) -> int:
        """
        Call the remote function.
        
        Args:
            args_blob: Raw binary data representing the arguments structure.
            
        Returns:
            int: The return value from the function.
        """
        # 1. Write Arguments
        self.dm.write_memory(self.args_addr, args_blob)
        
        # 2. Execute
        result = self.dm.execute(self.code_addr)
        
        # 3. Read Result (Optional? Protocol says EXEC returns value directly)
        # The protocol CMD_EXEC returns the 'int' return value of the function.
        # If the function returns data via pointer arguments, the user must read that manually
        # or we need a mechanism for that. 
        # For now, we just return the direct result.
        
        return result
