import struct
from typing import Any, Optional, Dict
from .smart_args import SmartArgs

class RemoteFunction:
    """
    Represents a function loaded on the remote device.
    """
    def __init__(self, device_manager, code_addr: int, args_addr: int, 
                 signature: Optional[Dict[str, Any]] = None, smart_args: bool = False):
        self.dm = device_manager
        self.code_addr = code_addr
        self.args_addr = args_addr
        self.signature = signature
        self.smart_args = smart_args

    def __call__(self, *args) -> Any:
        """
        Call the remote function.
        
        Args:
            *args: 
                If smart_args=False: Expects a single bytes object (args_blob).
                If smart_args=True: Expects variable arguments matching the function signature.
            
        Returns:
            The return value from the function.
        """
        if self.smart_args:
            if not self.signature:
                raise ValueError("Smart args enabled but no signature provided")
                
            handler = SmartArgs(self.dm, self.signature)
            try:
                # Pack arguments using SmartArgs
                args_blob = handler.pack(*args)
                
                # Write Arguments
                self.dm.write_memory(self.args_addr, args_blob)
                
                # Execute
                self.dm.execute(self.code_addr)
                
                # Read and convert return value
                return handler.get_return_value(self.args_addr)
                
            finally:
                # Cleanup allocated memory
                handler.cleanup()
                
        else:
            # Legacy mode: Expect single bytes argument
            if len(args) != 1 or not isinstance(args[0], bytes):
                raise ValueError("In legacy mode (smart_args=False), expected single bytes argument")
            
            args_blob = args[0]
            
            # 1. Write Arguments
            self.dm.write_memory(self.args_addr, args_blob)
            
            # 2. Execute
            result = self.dm.execute(self.code_addr)
            
            return result
