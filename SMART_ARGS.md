# Smart Args for P4-JIT

**Smart Args** is a feature that allows you to call C functions running on the ESP32-P4 directly from Python using NumPy arrays and scalars. It handles all the low-level memory management, type conversion, and binary packing automatically.

## Quick Start

Enable `smart_args=True` when loading a function:

```python
import numpy as np
from p4jit.runtime import JITSession

# 1. Connect
session = JITSession()
session.connect()

# 2. Load Function with Smart Args
# Assumes you have already built 'binary' using the Builder
remote_func = session.load_function(binary, args_addr, smart_args=True)

# 3. Call with NumPy types
data = np.array([10, 20, 30], dtype=np.int32)
length = np.int32(len(data))
scale = np.float32(1.5)

# The system automatically allocates memory for 'data' on the device
result = remote_func(data, length, scale)

print(f"Result: {result}")
```

## Supported Types

The system maps NumPy types to C types. All arguments are packed into 32-bit slots in the arguments buffer.

| Python / NumPy Type | C Type | C Definition | Notes |
| :--- | :--- | :--- | :--- |
| `np.int32`, `int` | `int`, `int32_t` | `int32_t` | Standard signed 32-bit integer. Range: -2,147,483,648 to 2,147,483,647. |
| `np.uint32` | `unsigned int`, `uint32_t` | `uint32_t` | Standard unsigned 32-bit integer. Range: 0 to 4,294,967,295. |
| `np.int16` | `short`, `int16_t` | `int16_t` | Packed as 32-bit. Sign-extended when read by C. |
| `np.uint16` | `unsigned short`, `uint16_t` | `uint16_t` | Packed as 32-bit. Zero-extended when read by C. |
| `np.int8` | `char`, `int8_t` | `int8_t` | Packed as 32-bit. Sign-extended when read by C. |
| `np.uint8` | `unsigned char`, `uint8_t` | `uint8_t` | Packed as 32-bit. Zero-extended when read by C. |
| `np.float32`, `float` | `float` | `float` | IEEE 754 Single Precision (32-bit). |
| `np.ndarray` (1D) | `type*` | `type*` | **Pointer**. Allocates array on device and passes the 32-bit address. |
| `np.ndarray` (0D) | `type` | `type` | **Value**. Extracts the scalar value from the 0-d array. |

> [!NOTE]
> **64-bit types** (`double`, `int64`) are currently **truncated to 32-bit** by the wrapper generator. Passing a `double` will result in a `float` on the device.

## Return Value Handling

The return value is passed back through the same arguments buffer used for inputs.

### Mechanism
1.  **Wrapper Execution**: The C wrapper executes your function.
2.  **Write Result**: The wrapper writes the return value to the **last slot (Index 31)** of the arguments buffer. This slot is at byte offset **124** (31 * 4).
3.  **Read & Convert**: `SmartArgs` reads these 4 bytes and converts them based on the function's return type.

### Type Conversion Table

| C Return Type | Raw Data Interpretation | Python Result Type | Example |
| :--- | :--- | :--- | :--- |
| `int`, `int32_t` | Signed 32-bit Integer (`<i`) | `np.int32` | `0xFFFFFFF6` -> `-10` |
| `uint32_t` | Unsigned 32-bit Integer (`<I`) | `np.uint32` | `0xFFFFFFF6` -> `4294967286` |
| `float` | IEEE 754 Float (`<f`) | `np.float32` | `0x40490FDB` -> `3.14159...` |
| `int8_t` | Signed 32-bit (Lower 8 bits used) | `np.int8` | Wrapper promotes `int8` to `int32`. Python reads `int32` then casts to `np.int8`. |
| `int16_t` | Signed 32-bit (Lower 16 bits used) | `np.int16` | Wrapper promotes `int16` to `int32`. Python reads `int32` then casts to `np.int16`. |
| `void` | Ignored | `None` | Returns Python `None`. |
| `*` (Pointer) | Unsigned 32-bit Address (`<I`) | `np.uint32` | Returns the memory address. |

## Architecture & Data Flow

When you call a remote function:

1.  **Validation**: `SmartArgs` checks if your Python arguments match the C function signature (extracted during the build process).
2.  **Allocation**:
    *   For **Array arguments** (pointers), memory is automatically allocated on the ESP32-P4 (in PSRAM).
    *   The array data is flattened and uploaded to the device.
3.  **Packing**:
    *   All arguments (scalar values and array pointers) are packed into a **128-byte Arguments Buffer**.
    *   Every argument takes up 4 bytes (32-bit alignment).
4.  **Execution**:
    *   The host sends the `EXEC` command.
    *   The **C Wrapper** on the device reads the arguments from the buffer, casts them, and calls your target function.
5.  **Return**:
    *   The wrapper writes the return value to the **last slot (Index 31)** of the arguments buffer.
    *   `SmartArgs` reads this slot, converts it back to the appropriate NumPy type, and returns it to Python.
6.  **Cleanup**:
    *   `SmartArgs` automatically frees all temporary memory allocated for arrays.

## Manual vs. Smart Args

| Feature | Manual (`smart_args=False`) | Smart Args (`smart_args=True`) |
| :--- | :--- | :--- |
| **Argument Packing** | You must use `struct.pack` manually. | Automatic. |
| **Memory Allocation** | You must call `device.allocate()` and `free()`. | Automatic for arrays. |
| **Type Safety** | None (raw bytes). | Checked against C signature. |
| **Return Value** | You must read memory manually. | Returned by function call. |

## Limitations

1.  **32-bit Only**: All arguments are passed as 32-bit values. `double` is cast to `float`, and `int64` is cast to `int32`.
2.  **Max Arguments**: The default buffer supports up to **31 arguments** (plus 1 slot for return value).
3.  **1D Arrays**: Multi-dimensional arrays are flattened. You must handle dimensions manually in your C code.
4.  **No Structs**: You cannot pass Python objects or C structs directly. You must manually pack them into a byte array if needed.
5.  **No Complex Pointers**: Pointers to pointers (`int**`), linked lists, or trees are not supported.
6.  **Strings**: Strings are treated as arrays of bytes (`int8`), not as native C strings.
7.  **Output Scalars**: To get a value back via a pointer argument (e.g., `void func(int *out)`), you must pass a 1-element array (e.g., `np.array([0], dtype=np.int32)`). Passing a scalar variable will not update the variable in Python.
