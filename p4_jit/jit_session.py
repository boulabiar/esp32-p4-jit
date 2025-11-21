import serial.tools.list_ports
from .device_manager import DeviceManager
from .remote_function import RemoteFunction

class JITSession:
    """
    Orchestrates the JIT session, handling device discovery and function loading.
    """
    def __init__(self):
        self.device = DeviceManager()

    def connect(self, port: str = None):
        """
        Connect to the device. If port is not specified, attempts to auto-detect
        by sending PING to available ports.
        """
        if port:
            self.device.port = port
            self.device.connect()
            if not self.device.ping():
                self.device.disconnect()
                raise RuntimeError(f"Device at {port} did not respond to PING")
        else:
            found = False
            ports = list(serial.tools.list_ports.comports())
            for p in ports:
                try:
                    self.device.port = p.device
                    self.device.connect()
                    if self.device.ping():
                        found = True
                        print(f"Found JIT Device at {p.device}")
                        break
                    self.device.disconnect()
                except Exception:
                    pass
            
            if not found:
                raise RuntimeError("Could not find JIT Device on any port")

    def load_function(self, binary_object, args_addr: int) -> RemoteFunction:
        """
        Load a compiled binary object onto the device.
        
        Args:
            binary_object: The BinaryObject from esp32_loader.builder
            args_addr: The address where arguments were allocated (DATA).
            
        Returns:
            RemoteFunction: Callable wrapper.
        """
        # 1. Validate
        # Check if base_address is in a valid CODE region
        # We can't easily check 'CODE' type here without querying DM's private table or exposing it.
        # But DM.write_memory will fail if it's not a valid allocation.
        
        # 2. Upload Code
        self.device.write_memory(binary_object.base_address, binary_object.data)
        
        # 3. Create Handle
        return RemoteFunction(self.device, binary_object.base_address, args_addr)
