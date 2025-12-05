# ESP32-P4 JIT System - Technical Reference Manual (TRM)

**Version**: 2.0.0  
**Target Architecture**: ESP32-P4 (RISC-V RV32IMAFC)  
**Last Updated**: January 2025  
**Audience**: System Integrators & Core Contributors

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Components](#2-system-components)
3. [Build System Deep Dive](#3-build-system-deep-dive)
4. [Wrapper System](#4-wrapper-system)
5. [Memory Management](#5-memory-management)
6. [Type System](#6-type-system)
7. [Smart Args System](#7-smart-args-system)
8. [Communication Protocol](#8-communication-protocol)
9. [Configuration](#9-configuration)
10. [Limitations & Constraints](#10-limitations--constraints)
11. [Advanced Topics](#11-advanced-topics)
12. [API Reference](#12-api-reference)
13. [Troubleshooting](#13-troubleshooting)
14. [Quick-Start Examples](#14-quick-start-examples)
15. [Appendices](#15-appendices)

---

## 1. Introduction

### 1.1 What is P4-JIT?

P4-JIT is a sophisticated dynamic code loading system for the ESP32-P4 microcontroller that enables developers to compile C/C++ code on a host PC and execute it natively on the device without reflashing the main firmware. Unlike interpreted languages (MicroPython, Lua) or bytecode virtual machines (WebAssembly), P4-JIT executes **native, optimized RISC-V machine code** directly on the processor.

The system provides a complete toolchain and runtime environment that handles:
- Cross-compilation using the standard ESP-IDF RISC-V toolchain
- Position-specific binary generation with automatic linker script generation
- High-speed USB transport (10-12 MB/s)
- Automatic cache coherency management
- Type-safe argument marshalling with NumPy integration
- Dynamic memory allocation with safety guarantees

This enables rapid prototyping, algorithm development, and deployment of computationally intensive tasks without the overhead of firmware compilation and flashing cycles.

**Key Capabilities**:
- **Native Performance**: Direct RISC-V instruction execution with zero interpreter overhead
- **Rapid Iteration**: Development cycle reduced from 30-60 seconds to 5-10 seconds
- **Smart Arguments**: Automatic type conversion and memory management for Python/NumPy integration
- **Multi-file Support**: Automatic discovery and compilation of multiple source files
- **Symbol Bridge**: Direct calling of firmware functions (printf, malloc, etc.)
- **Safety**: Host-side memory protection prevents device crashes
- **Flexibility**: Support for PSRAM and internal SRAM allocation

**Use Cases**:
- Digital Signal Processing (DSP) algorithm development
- Real-time control loop prototyping
- Machine learning inference kernel optimization
- Audio/video processing pipelines
- Cryptographic algorithm implementation
- Rapid hardware abstraction layer (HAL) testing

**Performance Characteristics**:
- **Code Upload**: ~100ms for 1MB binary
- **Function Call Overhead**: <10µs
- **USB Throughput**: 10-12 MB/s (High-Speed mode)
- **Execution Speed**: Native RISC-V performance (200MHz clock)

### 1.2 System Architecture

The P4-JIT system follows a client-server architecture split between the Host (development PC) and the Device (ESP32-P4 microcontroller).

![System Architecture](assets/system-architecture.png)

**Image Prompt for `assets/system-architecture.png`**:
```
Generate a professional system architecture diagram showing the P4-JIT system components. 

LEFT SIDE - Host PC (Blue Theme):
- Top: "Python Client" box containing "p4jit package"
- Middle: "Toolchain" box with sub-components:
  - Builder
  - Compiler (GCC)
  - Wrapper Generator
  - Linker Generator
- Bottom: "USB Driver" box

RIGHT SIDE - ESP32-P4 Device (Green Theme):
- Top: "USB Transport" box with "TinyUSB CDC-ACM"
- Middle: "Protocol Layer" box with:
  - Protocol Parser
  - Command Dispatcher
- Bottom: Two parallel boxes:
  - "Memory Manager" (heap_caps_*)
  - "Code Executor" (JIT Functions)

CENTER: Large bidirectional arrow labeled "USB High-Speed (12 Mbps)" connecting Host and Device

Add annotations:
- Host side: "Source Code (C/C++)" input arrow
- Device side: "Native RISC-V Execution" output
- Data flow arrows showing: Build → Link → Upload → Execute

Reference code structure:
- Host: host/p4jit/ directory
- Device: components/p4_jit/ directory

Use clear labels, professional color coding, and technical diagram style.
```

**High-Level Data Flow**:
1. **Source Code** → Host Toolchain → **Binary Object**
2. **Binary Object** → USB Transport → **Device Memory**
3. **Arguments** → USB Transport → **Args Buffer**
4. **Execute Command** → Device → **Function Execution**
5. **Return Value** → USB Transport → **Host Application**

### 1.3 Design Philosophy

#### 1.3.1 Why Position-Specific Code?

P4-JIT uses position-specific code rather than Position Independent Code (PIC) for several critical reasons:

**Performance**:
- PIC requires Global Offset Table (GOT) and Procedure Linkage Table (PLT)
- Every function call and data access requires indirection through GOT/PLT
- Additional memory accesses and instructions add 10-20% overhead
- Position-specific code uses direct addressing with zero overhead

**Simplicity**:
- No dynamic linker required on the embedded device
- Standard compiler output without special flags
- Straightforward memory management
- Predictable code generation

**Trade-off**:
- Requires knowing target address before linking (two-pass system)
- Cannot relocate code after linking
- Acceptable because we control allocation and linking process

#### 1.3.2 Why USB Over WiFi/UART?

**USB High-Speed (480 Mbps theoretical)**:
- Actual throughput: 10-12 MB/s
- Low latency: <1ms
- Built-in flow control
- No configuration required (plug-and-play)
- Reliable hardware protocol

**Compared to alternatives**:
- UART: 921600 baud = 115 KB/s (100x slower)
- WiFi: Higher latency, requires network setup, less reliable for large transfers

#### 1.3.3 Why Memory-Mapped I/O for Arguments?

**Problem**: Python cannot directly set RISC-V CPU registers

**Solution**: Shared memory buffer
- Host writes arguments to known memory address
- Device code reads from same address
- Simple, predictable, fast
- Works for any data type (with casting)

**Alternative rejected**: Dynamic stack manipulation (too complex, fragile)

#### 1.3.4 Why Automatic Wrapper Generation?

**Manual wrapper problems**:
- Error-prone type casting
- Boilerplate code for every function
- Difficult to maintain
- User must understand ABI details

**Automatic generation benefits**:
- Parse function signature once
- Generate type-safe casting code
- Consistent, tested implementation
- User focuses on algorithm, not plumbing

### 1.4 Key Features

#### 1.4.1 Native RISC-V Execution
- Direct machine code execution on RV32IMAFC core
- No interpretation or JIT compilation overhead
- Full access to hardware features (floating-point, atomic ops)
- Maximum performance for compute-intensive tasks

#### 1.4.2 Smart Argument Marshalling
- Automatic conversion between Python/NumPy types and C types
- Memory allocation for arrays handled transparently
- Bidirectional data sync (read-back modified arrays)
- Type validation at runtime prevents errors

#### 1.4.3 Multi-File Compilation
- Automatic discovery of source files in directory
- Support for C (.c), C++ (.cpp), and Assembly (.S)
- Link-Time Optimization (LTO) for cross-module inlining
- Single compilation command for complex projects

#### 1.4.4 Symbol Bridge (Firmware Linking)
- Call firmware functions from JIT code
- Zero overhead (direct address resolution at link time)
- Access to printf, malloc, FreeRTOS, ESP-IDF APIs
- No stub code or trampolines required

#### 1.4.5 Automatic Memory Management
- Shadow allocation table tracks all device memory
- Bounds checking prevents segmentation faults
- Automatic cleanup on function exit
- Host-side safety prevents device crashes

#### 1.4.6 Cache Coherency Handling
- Automatic cache synchronization after code upload
- Separate instruction and data cache management
- 128-byte cache line alignment
- Ensures CPU fetches correct instructions

---

## 2. System Components

### 2.1 Host Toolchain (`host/p4jit/`)

The host toolchain is responsible for transforming C/C++ source code into executable RISC-V machine code and managing the deployment to the device.

#### 2.1.1 Builder (`toolchain/builder.py`)

The Builder is the central orchestrator of the build process. It manages the entire pipeline from source files to binary objects.

**Responsibilities**:
- Load configuration from YAML
- Discover source files in directory
- Coordinate compilation of multiple files
- Generate linker scripts
- Extract and process binary sections
- Create BinaryObject with metadata

**Build Pipeline**:

![Builder Pipeline](assets/builder-pipeline.png)

**Image Prompt for `assets/builder-pipeline.png`**:
```
Generate a detailed flowchart showing the Builder pipeline from host/p4jit/toolchain/builder.py.

TOP TO BOTTOM FLOW:
1. START: "Entry Source File" (rounded rectangle)
2. PROCESS: "Load Configuration" (rectangle) - "toolchain.yaml"
3. PROCESS: "Discover Source Files" (rectangle) - "File Discovery Algorithm"
4. DECISION: "Multiple Files?" (diamond)
   - YES → "Compile Each File" (rectangle, loop back)
   - NO → Continue
5. PROCESS: "Generate Object Files" (rectangle) - ".o files"
6. PROCESS: "Generate Linker Script" (rectangle) - "LinkerGenerator"
7. PROCESS: "Link Object Files" (rectangle) - "GCC Linker"
8. PROCESS: "Extract Binary" (rectangle) - "objcopy"
9. PROCESS: "Process Sections" (rectangle) - "BinaryProcessor"
10. PROCESS: "Extract Symbols" (rectangle) - "SymbolExtractor"
11. PROCESS: "Validate Output" (rectangle) - "Validator"
12. END: "BinaryObject" (rounded rectangle)

Add side annotations:
- File Discovery: "Glob *.c, *.cpp, *.S"
- Linking: "Position-specific addresses"
- Validation: "Check size, alignment, entry point"

Use standard flowchart symbols with professional styling.
Reference: builder.py:build() method
```

**Multi-File Discovery Algorithm**:

```python
def _discover_source_files(self, source_dir):
    """
    Discover all compilable source files in directory.
    Returns sorted list for deterministic builds.
    """
    compile_extensions = self.config['extensions']['compile'].keys()
    discovered_files = []
    
    for ext in compile_extensions:
        pattern = os.path.join(source_dir, f'*{ext}')
        found = glob.glob(pattern)
        discovered_files.extend(found)
    
    # Sort for deterministic build order
    discovered_files.sort()
    return discovered_files
```

**Key Methods**:

`build(source, entry_point, base_address, optimization, output_dir, use_firmware_elf)`:
- Validates inputs (source exists, entry point valid, address aligned)
- Discovers all source files in directory
- Compiles each file to object (.o)
- Generates linker script with base address
- Links all objects with optional firmware symbols
- Extracts raw binary and processes sections
- Returns BinaryObject with complete metadata

**Configuration Loading**:
- Loads `config/toolchain.yaml`
- Resolves relative paths from project root
- Provides defaults for optional fields
- Validates toolchain paths exist

#### 2.1.2 Compiler (`toolchain/compiler.py`)

The Compiler wraps the RISC-V GCC toolchain and handles all compilation, linking, and binary extraction operations.

**Purpose**:
- Abstract GCC command-line interface
- Manage compiler flags and options
- Handle include paths automatically
- Support multiple languages (C, C++, Assembly)

**Extension-to-Compiler Mapping**:

The compiler automatically selects the correct compiler based on file extension:

| Extension | Compiler | Use Case |
|-----------|----------|----------|
| `.c` | `riscv32-esp-elf-gcc` | C source files |
| `.cpp`, `.cc`, `.cxx` | `riscv32-esp-elf-g++` | C++ source files |
| `.S` | `riscv32-esp-elf-gcc` | Assembly with C preprocessor |

Configuration from `config/toolchain.yaml:extensions:compile`

**Compilation Process**:

```python
def compile(self, source, output, optimization='O2'):
    """
    Compile source file to object file.
    Automatically derives include path from source directory.
    """
    ext = os.path.splitext(source)[1]
    compile_map = self.config['extensions']['compile']
    
    if ext not in compile_map:
        raise ValueError(f"Unknown extension: {ext}")
    
    compiler_name = compile_map[ext]
    compiler_path = self.compilers[compiler_name]
    
    # Derive include directory from source file
    source_dir = os.path.dirname(os.path.abspath(source))
    include_flag = f'-I{source_dir}'
    
    arch = self.config['compiler']['arch']
    abi = self.config['compiler']['abi']
    flags = self.config['compiler']['flags']
    
    cmd = [
        compiler_path,
        f'-march={arch}',
        f'-mabi={abi}',
        f'-{optimization}',
        '-g',              # Debug symbols
        include_flag,
        '-c',              # Compile only
        source,
        '-o', output
    ] + flags
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Compilation failed:\n{result.stderr}")
```

**GCC Flags Explained**:

| Flag | Purpose |
|------|---------|
| `-march=rv32imafc_zicsr_zifencei_xesppie` | Target ISA extensions |
| `-mabi=ilp32f` | ABI: 32-bit int/long/pointer, float in FP regs |
| `-O3` | Maximum optimization |
| `-g` | Generate debug symbols |
| `-ffreestanding` | No standard library assumptions |
| `-fno-builtin` | Disable built-in functions |
| `-ffunction-sections` | Place each function in separate section |
| `-fdata-sections` | Place each data item in separate section |
| `-msmall-data-limit=0` | Disable small data optimization |
| `-flto` | Enable Link-Time Optimization |

**Linking Process**:

```python
def link(self, obj_files, linker_script, output, use_firmware_elf=True):
    """
    Link multiple object files with custom linker script.
    Optionally resolve symbols against firmware ELF.
    """
    arch = self.config['compiler']['arch']
    abi = self.config['compiler']['abi']
    linker_flags = self.config['linker']['flags']
    firmware_elf = self.config.get('linker', {}).get('firmware_elf')
    
    cmd = [
        self.compilers['gcc'],
        f'-march={arch}',
        f'-mabi={abi}',
        f'-T{linker_script}'
    ]
    
    # Add firmware symbols if configured
    if use_firmware_elf and firmware_elf:
        if not os.path.exists(firmware_elf):
            raise FileNotFoundError(
                f"Firmware ELF not found: {firmware_elf}\n"
                f"Update 'linker:firmware_elf' in config/toolchain.yaml"
            )
        cmd.append(f'-Wl,-R,{firmware_elf}')
    
    cmd += obj_files + ['-o', output] + linker_flags
    
    if self.config['linker']['garbage_collection']:
        cmd.append('-Wl,--gc-sections')
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Linking failed:\n{result.stderr}")
```

**Binary Extraction**:

```python
def extract_binary(self, elf_file, output):
    """
    Extract raw binary from ELF file using objcopy.
    Strips all headers and debug information.
    """
    cmd = [
        self.objcopy,
        '-O', 'binary',  # Output format
        elf_file,
        output
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Binary extraction failed:\n{result.stderr}")
    
    with open(output, 'rb') as f:
        return f.read()
```

#### 2.1.3 Linker Generator (`toolchain/linker_gen.py`)

The Linker Generator creates custom GNU LD linker scripts that specify exactly where code and data should be placed in memory.

**Purpose**:
- Define memory regions (address and size)
- Control section placement (.text, .data, .rodata, .bss)
- Set entry point
- Enable position-specific linking

**Template Structure** (`templates/linker.ld.template`):

```ld
ENTRY({ENTRY_POINT})

MEMORY
{
    SRAM (rwx) : ORIGIN = {BASE_ADDRESS}, LENGTH = {MEMORY_SIZE}
}

SECTIONS
{
    .text {BASE_ADDRESS} : ALIGN(4)
    {
        *(.text.{ENTRY_POINT})   /* Entry point first */
        *(.text*)                 /* All other code */
        *(.literal*)              /* RISC-V literals */
    } > SRAM

    .rodata : ALIGN(4)
    {
        *(.rodata*)               /* Read-only data */
    } > SRAM

    .data : ALIGN(4)
    {
        *(.data*)                 /* Initialized data */
    } > SRAM

    .bss : ALIGN(4)
    {
        __bss_start = .;
        *(.bss*)                  /* Uninitialized data */
        *(COMMON)
        __bss_end = .;
    } > SRAM
    
    __binary_end = .;

    /DISCARD/ :
    {
        *(.comment)
        *(.note*)
        *(.eh_frame*)             /* Exception handling (not needed) */
        *(.riscv.attributes)
    }
}
```

**Template Variables**:
- `{ENTRY_POINT}`: Function name (e.g., `call_remote`)
- `{BASE_ADDRESS}`: Load address in hex (e.g., `0x40800000`)
- `{MEMORY_SIZE}`: Maximum size (e.g., `128K`)

**Section Placement Strategy**:
1. `.text`: Code placed first at exact base address
2. `.rodata`: Immediately after code (read-only data, constants)
3. `.data`: Initialized global/static variables
4. `.bss`: Uninitialized variables (zero-filled at runtime)

**Why Exact Addresses Matter**:
- RISC-V uses PC-relative addressing for branches
- Absolute addresses for function pointers and data references
- Incorrect placement causes jumps to wrong locations

#### 2.1.4 Binary Processor (`toolchain/binary_processor.py`)

The Binary Processor extracts section information from ELF files and handles BSS padding for uninitialized data.

**Section Extraction**:

Uses `readelf` to parse ELF section headers:

```python
def extract_sections(self, elf_file):
    """
    Extract section information from ELF file.
    Returns dict: {section_name: {address, size, type}}
    """
    cmd = [self.readelf, '-S', elf_file]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    sections = {}
    
    for line in result.stdout.split('\n'):
        # Parse format: [Nr] Name Type Addr Off Size
        match = re.search(
            r'\[\s*\d+\]\s+(\.[\w.]+)\s+(\w+)\s+([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)',
            line
        )
        
        if match:
            name = match.group(1)
            sect_type = match.group(2)
            address = int(match.group(3), 16)
            size = int(match.group(4), 16)
            
            if name in ['.text', '.rodata', '.data', '.bss']:
                sections[name] = {
                    'address': address,
                    'size': size,
                    'type': sect_type
                }
    
    return sections
```

**BSS Padding**:

The `.bss` section is not stored in the binary file (it's uninitialized). We must append zeros to reserve space:

```python
def pad_bss(self, binary_data, sections):
    """
    Pad binary with zeros for alignment and BSS sections.
    Ensures all memory is properly initialized.
    """
    # First, align to 4-byte boundary
    alignment_padding = (4 - (len(binary_data) % 4)) % 4
    
    # Then add BSS size (NOBITS sections)
    bss_size = sum(
        s['size'] for s in sections.values() 
        if s['type'] == 'NOBITS'
    )
    
    total_padding = alignment_padding + bss_size
    
    return binary_data + b'\x00' * total_padding
```

**Why BSS Padding Matters**:
- Global variables like `int counter = 0;` go in BSS
- Without padding, device memory is uninitialized (garbage values)
- Padding ensures zero-initialization as per C standard

#### 2.1.5 Symbol Extractor (`toolchain/symbol_extractor.py`)

The Symbol Extractor reads the symbol table from ELF files to identify functions and their addresses.

**Symbol Extraction Using `nm`**:

```python
def extract_all_symbols(self, elf_file):
    """
    Extract all symbols from ELF file.
    Returns list of dicts: [{name, address, size, type}, ...]
    """
    cmd = [self.nm, '--print-size', '--size-sort', elf_file]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    symbols = []
    
    for line in result.stdout.split('\n'):
        parts = line.split()
        
        if len(parts) >= 4:
            address = int(parts[0], 16)
            size = int(parts[1], 16)
            type_char = parts[2]
            name = ' '.join(parts[3:])
            
            # Convert nm type to symbol type
            if type_char in ['T', 't']:      # Text (code)
                sym_type = 'FUNC'
            elif type_char in ['D', 'd', 'B', 'b', 'R', 'r', 'C', 'c']:
                sym_type = 'OBJECT'          # Data/BSS
            else:
                continue
            
            symbols.append({
                'name': name,
                'address': address,
                'size': size,
                'type': sym_type
            })
    
    return symbols
```

**Function Address Resolution**:

```python
def get_function_address(self, elf_file, function_name):
    """
    Get address of specific function.
    Returns None if not found.
    """
    symbols = self.extract_all_symbols(elf_file)
    
    for symbol in symbols:
        if symbol['name'] == function_name and symbol['type'] == 'FUNC':
            return symbol['address']
    
    # Not found - provide debug info
    funcs = [s for s in symbols if s['type'] == 'FUNC']
    logger.error(f"Function '{function_name}' not found")
    logger.info(f"Available functions ({len(funcs)}):")
    
    for func in sorted(funcs, key=lambda x: x['address']):
        logger.info(
            f"  {func['name']:50s} "
            f"0x{func['address']:08x} "
            f"({func['size']:4d} bytes)"
        )
    
    return None
```

#### 2.1.6 Wrapper Generator (`toolchain/wrapper_generator.py`)

The Wrapper Generator is one of the most critical components. It automatically generates C code that bridges the gap between Python and the target function.

**The Problem It Solves**:

Python cannot directly set RISC-V CPU registers (a0-a7, fa0-fa7). The wrapper provides a memory-based interface where:
1. Python writes arguments to a memory buffer
2. Wrapper reads from buffer and casts to correct types
3. Wrapper calls target function with ABI-correct arguments
4. Wrapper writes return value back to buffer
5. Python reads return value from buffer

**Memory Layout**:

![Wrapper Memory Layout](assets/wrapper-memory-layout.png)

**Image Prompt for `assets/wrapper-memory-layout.png`**:
```
Create a detailed technical diagram of the wrapper args buffer memory structure.

MAIN SECTION - Args Buffer:
- Title: "Args Buffer (128 bytes)"
- Show vertical bar representing memory from offset 0x00 to 0x7C
- Divide into 32 horizontal slots, each 4 bytes
- Label left side with byte offsets: 0x00, 0x04, 0x08, ..., 0x7C
- Label right side with slot indices: [0], [1], [2], ..., [31]

SLOT ANNOTATIONS:
- Slots [0-30]: Green background, label "Argument Slots"
- Slot [31] (0x7C): Red background, label "Return Value Slot"

EXAMPLE DATA (inset box):
Show 3 arguments being passed:
- Slot [0] = 0x30100000 (pointer, 32-bit address)
- Slot [1] = 0xFFFFFFD6 (int32, -42 in two's complement)
- Slot [2] = 0x40490FDB (float32, 3.14159... in IEEE 754)
- Slot [31] = 0x00000042 (return: int32, 66)

ANNOTATIONS:
- Add arrow: "Base Address (arg_address)" pointing to offset 0x00
- Add note: "4-byte alignment, Little-endian"
- Add formula: "slot_offset = index × 4"
- Add note: "All types packed to 32-bit slots"

LEGEND:
- Green: "Read by wrapper (input)"
- Red: "Written by wrapper (output)"
- Gray: "Unused (if < 31 args)"

Reference: wrapper_generator.py:_generate_arg_reads() and _generate_result_write()
Use professional technical diagram style with clear grid lines.
```

**Wrapper Code Structure**:

Complete generated wrapper example for `float sum_point(Point* p, int8_t z, uint16_t* arr)`:

```c
// Auto-generated wrapper for sum_point
// Generated by esp32-jit wrapper system
// Args array size: 32 slots (128 bytes)
// Arguments: 3 (slots 0-2)
// Return value: slot 31

#include <stdint.h>
#include "geometry.h"  // Include generated header

typedef int esp_err_t;
#define ESP_OK 0

esp_err_t call_remote(void) {
    volatile int32_t *io = (volatile int32_t *)0x48211640;

    // Argument 0: POINTER type Point*
    Point* p = (Point*) io[0];

    // Argument 1: VALUE type int8_t
    int8_t z = *(int8_t*)& io[1];

    // Argument 2: POINTER type uint16_t*
    uint16_t* arr = (uint16_t*) io[2];

    // Call original function: sum_point
    float result = sum_point(p, z, arr);

    // Write result (float) to slot 31
    *(float*)&io[31] = result;

    return ESP_OK;
}
```

**Argument Reading Logic**:

For each parameter type, different casting is required:

| C Type | Category | Wrapper Code |
|--------|----------|--------------|
| `int*`, `float*` | Pointer | `Type* name = (Type*) io[N];` |
| `int32_t`, `uint32_t` | Integer | `Type name = *(Type*)& io[N];` |
| `int16_t`, `uint16_t` | Short | `Type name = *(Type*)& io[N];` (sign/zero extended) |
| `int8_t`, `uint8_t` | Byte | `Type name = *(Type*)& io[N];` (sign/zero extended) |
| `float` | Float | `float name = *(float*)& io[N];` (bit pattern preserved) |

**Return Value Writing Logic**:

```python
def _generate_result_write(self):
    """Generate code to write result to I/O memory."""
    return_type = self.signature['return_type']
    return_idx = self.calculate_return_index()  # Always 31
    
    if return_type == 'void':
        return "    // No return value (void function)\n"
    
    lines = [f"    // Write result ({return_type}) to slot {return_idx}"]
    
    if '*' in return_type:
        # Pointers: cast to uint32_t
        lines.append(f"    *(uint32_t*)&io[{return_idx}] = (uint32_t)result;")
    elif return_type == 'float':
        # Float: direct write preserves bit pattern
        lines.append(f"    *(float*)&io[{return_idx}] = result;")
    elif return_type == 'double':
        # Double: truncate to float (32-bit limitation)
        lines.append(f"    *(float*)&io[{return_idx}] = (float)result;")
    else:
        # Integers: type-specific write handles sign extension
        lines.append(f"    *({return_type}*)&io[{return_idx}] = result;")
    
    return '\n'.join(lines) + '\n'
```

**Why Volatile?**

```c
volatile int32_t *io = (volatile int32_t *)0x48211640;
```

The `volatile` qualifier is critical:
- Prevents compiler from caching values in registers
- Forces actual memory read/write on each access
- Necessary when memory may be modified externally (by Python host)

**Complete Generation Flow**:

```python
def generate_wrapper(self):
    """Generate complete wrapper code."""
    self.validate_args_count()
    
    code_parts = []
    
    code_parts.append(self._generate_header())
    code_parts.append(self._generate_includes())
    code_parts.append(self._generate_function_start())
    code_parts.append(self._generate_io_pointer())
    code_parts.append(self._generate_arg_reads())
    code_parts.append(self._generate_function_call())
    code_parts.append(self._generate_result_write())
    code_parts.append(self._generate_function_end())
    
    return '\n'.join(code_parts)
```

#### 2.1.7 Signature Parser (`toolchain/signature_parser.py`)

The Signature Parser extracts function signatures from C source code using a combination of regex and pycparser.

**Parsing Strategy**:

Two-stage approach:
1. **Regex extraction**: Find function definition line(s)
2. **pycparser parsing**: Parse signature into AST

**Regex Extraction Algorithm**:

```python
def _extract_signature_string(self, source_code, func_name):
    """
    Extract function signature from source code.
    Handles multi-line signatures.
    """
    lines = source_code.splitlines()
    
    for i, line in enumerate(lines):
        if func_name not in line:
            continue
        
        # Check if this looks like a definition
        idx = line.find(func_name)
        rest = line[idx + len(func_name):].strip()
        
        if not rest.startswith('('):
            continue  # Probably a function call, not definition
        
        # Capture return type (text before name)
        return_type_part = line[:idx].strip()
        
        # Capture arguments (may span multiple lines)
        combined_text = source_code[source_code.find(line):]
        
        # Find matching closing parenthesis
        balance = 0
        args_end_idx = -1
        start_paren = combined_text.find('(')
        
        for j, char in enumerate(combined_text[start_paren:]):
            if char == '(':
                balance += 1
            elif char == ')':
                balance -= 1
                if balance == 0:
                    args_end_idx = start_paren + j
                    break
        
        if args_end_idx != -1:
            args_part = combined_text[start_paren:args_end_idx+1]
            prototype_str = f"{return_type_part} {func_name}{args_part};"
            return prototype_str
    
    return None
```

**pycparser Integration**:

```python
def parse_function(self, function_name):
    """
    Parse function signature using pycparser.
    Returns dict with name, return_type, parameters.
    """
    self.current_function = function_name
    
    with open(self.source_file, 'r') as f:
        source_code = f.read()
    
    # Extract signature string
    signature_str = self._extract_signature_string(source_code, function_name)
    
    if not signature_str:
        raise ValueError(f"Function '{function_name}' not found")
    
    # Prepend standard types for parsing
    full_code = self.std_types + "\n" + signature_str
    
    # Parse with pycparser
    parser = c_parser.CParser()
    ast = parser.parse(full_code, filename='<extracted>')
    
    # Extract from AST
    for node in ast.ext:
        if isinstance(node, c_ast.FuncDef) and node.decl.name == function_name:
            return self._extract_signature_from_ast(node)
    
    raise ValueError(f"Parsed but function '{function_name}' not found in AST")
```

**Type Classification**:

```python
def classify_parameter(self, type_str):
    """
    Classify parameter as 'value' or 'pointer'.
    """
    if '*' in type_str or '[]' in type_str:
        return 'pointer'
    else:
        return 'value'
```

**Custom Typedefs**:

The parser prepends `config/std_types.h` before parsing:

```c
typedef signed char int8_t;
typedef short int int16_t;
typedef long int int32_t;
// ... (standard types)

typedef struct {
    float x;
    int y;
} Point;  // Custom typedef
```

This ensures pycparser can resolve all types in the signature.

#### 2.1.8 Header Generator (`toolchain/header_generator.py`)

The Header Generator creates C header files with function prototypes, enabling the wrapper to call the original function.

**Generated Header Structure**:

For function `float sum_point(Point* p, int8_t z, uint16_t* arr)` in `geometry.c`:

```c
#ifndef GEOMETRY_H
#define GEOMETRY_H

// Auto-generated header for sum_point
// Source: geometry.c

#include "std_types.h"

// Function declaration
float sum_point(Point* p, int8_t z, uint16_t* arr);

#endif // GEOMETRY_H
```

**Generation Logic**:

```python
def generate_header(self):
    """Generate complete header file content."""
    parts = []
    
    parts.append(self._generate_header_guard_start())
    parts.append(self._generate_header_comment())
    parts.append(self._generate_typedefs())
    parts.append(self._generate_function_declaration())
    parts.append(self._generate_header_guard_end())
    
    return '\n'.join(parts)

def _generate_function_declaration(self):
    """Generate function prototype."""
    func_name = self.signature['name']
    return_type = self.signature['return_type']
    
    params = []
    for param in self.signature['parameters']:
        param_type = param['type']
        param_name = param['name']
        params.append(f"{param_type} {param_name}")
    
    params_str = ', '.join(params) if params else 'void'
    
    return f"{return_type} {func_name}({params_str});"
```

#### 2.1.9 Metadata Generator (`toolchain/metadata_generator.py`)

The Metadata Generator creates `signature.json` files containing complete function signature and memory layout information for Smart Args.

**Metadata Structure**:

```json
{
  "name": "sum_point",
  "return_type": "float",
  "parameters": [
    {
      "index": 0,
      "name": "p",
      "type": "Point*",
      "category": "pointer"
    },
    {
      "index": 1,
      "name": "z",
      "type": "int8_t",
      "category": "value"
    },
    {
      "index": 2,
      "name": "arr",
      "type": "uint16_t*",
      "category": "pointer"
    }
  ],
  "addresses": {
    "code_base": "0x48211000",
    "arg_base": "0x48211640",
    "args_array_size": 32,
    "args_array_bytes": 128
  },
  "arguments": [
    {
      "index": 0,
      "name": "p",
      "type": "Point*",
      "category": "pointer",
      "address": "0x48211640"
    },
    {
      "index": 1,
      "name": "z",
      "type": "int8_t",
      "category": "value",
      "address": "0x48211644"
    },
    {
      "index": 2,
      "name": "arr",
      "type": "uint16_t*",
      "category": "pointer",
      "address": "0x48211648"
    }
  ],
  "result": {
    "type": "float",
    "index": 31,
    "address": "0x4821167C"
  }
}
```

**Address Calculation**:

```python
def calculate_addresses(self):
    """Calculate memory addresses for arguments and return value."""
    addresses = {
        'arguments': [],
        'return': {}
    }
    
    # Arguments
    for idx, param in enumerate(self.signature['parameters']):
        addr = self.arg_address + (idx * 4)
        addresses['arguments'].append({
            'index': idx,
            'name': param['name'],
            'type': param['type'],
            'category': param['category'],
            'address': f"0x{addr:08x}"
        })
    
    # Return value (always at last slot)
    return_idx = self.args_array_size - 1
    return_addr = self.arg_address + (return_idx * 4)
    addresses['return'] = {
        'type': self.signature['return_type'],
        'index': return_idx,
        'address': f"0x{return_addr:08x}"
    }
    
    return addresses
```

#### 2.1.10 Validator (`toolchain/validator.py`)

The Validator performs various sanity checks during the build process to catch errors early.

**Validation Checks**:

1. **Address Alignment**:
```python
def validate_address(self, address):
    """Ensure address is properly aligned."""
    if address % self.alignment != 0:
        raise ValueError(
            f"Address 0x{address:08x} not {self.alignment}-byte aligned"
        )
```

2. **Source File Existence**:
```python
def validate_source(self, source_file):
    """Check that source file exists."""
    if not os.path.exists(source_file):
        raise FileNotFoundError(f"Source file not found: {source_file}")
```

3. **Entry Point Validity**:
```python
def validate_entry_point(self, entry_point):
    """Ensure entry point is valid identifier."""
    if not entry_point or not entry_point.isidentifier():
        raise ValueError(f"Invalid entry point: {entry_point}")
```

4. **Output Size**:
```python
def validate_output(self, sections, base_address):
    """Check total size and section placement."""
    total_size = sum(info['size'] for info in sections.values())
    
    if total_size > self.max_size:
        raise ValueError(
            f"Total size {total_size} exceeds max {self.max_size}"
        )
    
    for name, info in sections.items():
        if info['address'] < base_address:
            raise ValueError(f"Section {name} below base address")
```

#### 2.1.11 Binary Object (`toolchain/binary_object.py`)

The BinaryObject encapsulates the compiled binary and all associated metadata, providing a clean API for inspection and export.

**Properties**:

```python
@property
def data(self):
    """Raw binary data as bytes."""
    return self._data

@property
def total_size(self):
    """Total size including BSS padding."""
    return len(self._data)

@property
def base_address(self):
    """Base load address."""
    return self._base_address

@property
def entry_address(self):
    """Entry point address."""
    return self._entry_address

@property
def sections(self):
    """Dictionary of section info."""
    return self._sections

@property
def functions(self):
    """List of all functions with addresses."""
    return [s for s in self._symbols if s.get('type') == 'FUNC']
```

**Export Methods**:

```python
def save_bin(self, path):
    """Save raw binary to file."""
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'wb') as f:
        f.write(self._data)

def save_elf(self, path):
    """Copy ELF file with debug symbols."""
    shutil.copy(self._elf_path, path)

def save_metadata(self, path):
    """Save metadata as JSON."""
    metadata = self.get_metadata_dict()
    with open(path, 'w') as f:
        json.dump(metadata, f, indent=2)
```

**Inspection Methods**:

```python
def disassemble(self, output=None, source_intermix=True):
    """Disassemble code using objdump."""
    cmd = [self._objdump, '-d']
    if source_intermix:
        cmd.append('-S')  # Intermix source code
    cmd.append(self._elf_path)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if output:
        with open(output, 'w') as f:
            f.write(result.stdout)
    else:
        print(result.stdout)

def print_memory_map(self):
    """Print visual memory map."""
    logger.info(f"Memory Map (Base: 0x{self._base_address:08x}):")
    logger.info("  " + "─" * 60)
    
    for name, info in sorted(self._sections.items(), 
                             key=lambda x: x[1]['address']):
        offset = info['address'] - self._base_address
        size = info['size']
        
        logger.info(f"  {offset:6d}  │ {name:12s} {size:6d} bytes")
    
    logger.info("  " + "─" * 60)
    logger.info(f"  Total: {self.total_size} bytes")
```

### 2.2 Device Firmware (`components/p4_jit/`)

The device firmware implements the server side of the P4-JIT system, handling protocol parsing, memory management, and code execution.

#### 2.2.1 Component Structure

**CMakeLists.txt**:

```cmake
idf_component_register(
    SRCS 
        "src/p4_jit.c"
        "src/commands.c"
        "src/protocol.c"
        "src/usb_transport.c"
    INCLUDE_DIRS 
        "include" 
        "src"
    REQUIRES 
        esp_timer 
        driver 
        esp_rom 
        esp_mm 
        heap 
        log
)
```

**Kconfig Options**:

```kconfig
menu "P4-JIT Configuration"

    config P4_JIT_TASK_STACK_SIZE
        int "JIT Task Stack Size"
        default 8192
        help
            Stack size for the task handling USB protocol and JIT commands.

    config P4_JIT_TASK_PRIORITY
        int "JIT Task Priority"
        default 5
        help
            Priority of the JIT task. Higher number = higher priority.

    config P4_JIT_TASK_CORE_ID
        int "JIT Task Core ID"
        default 1
        range -1 1
        help
            Core to pin the JIT task to. -1 = No Affinity, 0 = Core 0, 1 = Core 1.

    config P4_JIT_PAYLOAD_BUFFER_SIZE
        int "JIT Payload Buffer Size"
        default 1048576
        help
            Size of the RX/TX buffers for JIT commands (default 1MB).

    config P4_JIT_STREAM_BUFFER_SIZE
        int "USB Stream Buffer Size"
        default 16384
        help
            Size of the internal FreeRTOS StreamBuffer for USB ISR (default 16KB).

endmenu
```

**Dependencies**:

From `idf_component.yml`:
```yaml
dependencies:
  idf:
    version: '>=4.1.0'
  espressif/esp_tinyusb: '*'
```

#### 2.2.2 Main Entry Point (`src/p4_jit.c`)

The main entry point initializes the system and spawns the protocol task.

```c
#include "p4_jit.h"
#include "protocol.h"
#include "usb_transport.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"

static const char *TAG = "p4_jit";
static TaskHandle_t s_jit_task_handle = NULL;

static void jit_task_entry(void *arg) {
    ESP_LOGI(TAG, "JIT Task started on Core %d", xPortGetCoreID());
    protocol_loop();  // Infinite loop
    vTaskDelete(NULL);
}

esp_err_t p4_jit_start(const p4_jit_config_t *config) {
    if (s_jit_task_handle != NULL) {
        ESP_LOGW(TAG, "JIT engine already running");
        return ESP_ERR_INVALID_STATE;
    }

    // Load configuration (with defaults from Kconfig)
    int priority = CONFIG_P4_JIT_TASK_PRIORITY;
    int core_id = CONFIG_P4_JIT_TASK_CORE_ID;
    int stack_size = CONFIG_P4_JIT_TASK_STACK_SIZE;

    if (config) {
        if (config->task_priority > 0) priority = config->task_priority;
        if (config->task_core_id >= -1) core_id = config->task_core_id;
        if (config->stack_size > 0) stack_size = config->stack_size;
    }

    ESP_LOGI(TAG, "Initializing USB Transport...");
    usb_transport_init();

    ESP_LOGI(TAG, "Starting JIT Task (Prio:%d, Core:%d, Stack:%d)", 
             priority, core_id, stack_size);
    
    BaseType_t ret = xTaskCreatePinnedToCore(
        jit_task_entry,
        "jit_task",
        stack_size,
        NULL,
        priority,
        &s_jit_task_handle,
        core_id
    );

    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create JIT task");
        return ESP_FAIL;
    }

    return ESP_OK;
}
```

**Configuration Structure**:

```c
typedef struct {
    int task_priority;      // FreeRTOS priority (0-25)
    int task_core_id;       // CPU core (0, 1, or tskNO_AFFINITY)
    int stack_size;         // Stack size in bytes
    size_t rx_buffer_size;  // Reserved
    size_t tx_buffer_size;  // Reserved
} p4_jit_config_t;
```

#### 2.2.3 Protocol Handler (`src/protocol.c`)

The protocol handler implements the packet-based binary protocol over USB.

![Protocol State Machine](assets/protocol-state-machine.png)

**Image Prompt for `assets/protocol-state-machine.png`**:
```
Generate a state machine diagram for the protocol handler from components/p4_jit/src/protocol.c:protocol_loop().

STATES (rounded rectangles):
1. "Wait for Magic[0]" (start state, double border)
2. "Wait for Magic[1]"
3. "Read Header" (6 bytes)
4. "Read Payload" (N bytes)
5. "Read Checksum" (2 bytes)
6. "Verify Checksum" (decision diamond)
7. "Dispatch Command" (rectangle)
8. "Send Response" (rectangle)

TRANSITIONS:
- "Wait for Magic[0]" → "Wait for Magic[1]" (condition: "byte == 0xA5")
- "Wait for Magic[0]" ← loop (condition: "byte != 0xA5")
- "Wait for Magic[1]" → "Read Header" (condition: "byte == 0x5A")
- "Wait for Magic[1]" → "Wait for Magic[0]" (condition: "byte != 0x5A")
- "Read Header" → "Read Payload" (condition: "len > 0")
- "Read Header" → "Read Checksum" (condition: "len == 0")
- "Read Payload" → "Read Checksum"
- "Read Checksum" → "Verify Checksum"
- "Verify Checksum" → "Dispatch Command" (condition: "OK")
- "Verify Checksum" → "Send Error Response" → "Wait for Magic[0]" (condition: "FAIL")
- "Dispatch Command" → "Send Response"
- "Send Response" → "Wait for Magic[0]" (loop back)

ERROR PATHS (red dashed lines):
- From any state: "Timeout" → "Wait for Magic[0]"

Add annotations:
- "USB Read (Blocking)"
- "Calculate Checksum"
- "ERR_CHECKSUM on mismatch"

Use standard FSM notation with clear labels and colors.
```

**Protocol Loop Implementation**:

```c
void protocol_loop(void) {
    // Allocate buffers
    rx_buffer = malloc(MAX_PAYLOAD_SIZE);
    tx_buffer = malloc(MAX_PAYLOAD_SIZE);
    
    if (!rx_buffer || !tx_buffer) {
        ESP_LOGE(TAG, "Failed to allocate buffers");
        return;
    }

    ESP_LOGI(TAG, "Protocol loop started");

    while (1) {
        // 1. Sync: Look for Magic bytes
        uint8_t byte;
        usb_read_bytes(&byte, 1);
        if (byte != MAGIC_BYTE_1) continue;
        
        usb_read_bytes(&byte, 1);
        if (byte != MAGIC_BYTE_2) continue;

        // 2. Read rest of header (6 bytes: cmd, flags, len)
        packet_header_t header;
        header.magic[0] = MAGIC_BYTE_1;
        header.magic[1] = MAGIC_BYTE_2;
        usb_read_bytes(&header.cmd_id, 1);
        usb_read_bytes(&header.flags, 1);
        usb_read_bytes((uint8_t*)&header.payload_len, 4);

        // 3. Read Payload
        if (header.payload_len > MAX_PAYLOAD_SIZE) {
            ESP_LOGE(TAG, "Payload too large: %lu", header.payload_len);
            continue;
        }
        
        if (header.payload_len > 0) {
            usb_read_bytes(rx_buffer, header.payload_len);
        }

        // 4. Read Checksum
        uint16_t received_checksum;
        usb_read_bytes((uint8_t*)&received_checksum, 2);

        // 5. Verify Checksum
        uint16_t calc_checksum = calculate_checksum(
            (uint8_t*)&header, sizeof(header)
        );
        if (header.payload_len > 0) {
            calc_checksum += calculate_checksum(
                rx_buffer, header.payload_len
            );
        }

        if (calc_checksum != received_checksum) {
            ESP_LOGE(TAG, "Checksum mismatch");
            uint32_t err = ERR_CHECKSUM;
            send_response(header.cmd_id, 0x02, (uint8_t*)&err, 4);
            continue;
        }

        // 6. Dispatch Command
        uint32_t out_len = 0;
        uint32_t err_code = dispatch_command(
            header.cmd_id, 
            rx_buffer, 
            header.payload_len, 
            tx_buffer, 
            &out_len
        );

        // 7. Send Response
        if (err_code != ERR_OK) {
            send_response(header.cmd_id, 0x02, (uint8_t*)&err_code, 4);
        } else {
            send_response(header.cmd_id, 0x01, tx_buffer, out_len);
        }
    }
}
```

**Checksum Calculation**:

```c
static uint16_t calculate_checksum(const uint8_t *data, size_t len) {
    uint16_t sum = 0;
    for (size_t i = 0; i < len; i++) {
        sum += data[i];
    }
    return sum & 0xFFFF;
}
```

**Response Generation**:

```c
void send_response(uint8_t cmd_id, uint8_t flags, 
                   uint8_t *payload, uint32_t len) {
    // 1. Construct Header
    packet_header_t header;
    header.magic[0] = MAGIC_BYTE_1;
    header.magic[1] = MAGIC_BYTE_2;
    header.cmd_id = cmd_id;
    header.flags = flags;
    header.payload_len = len;

    // 2. Calculate Checksum
    uint16_t checksum = calculate_checksum((uint8_t*)&header, sizeof(header));
    if (payload && len > 0) {
        checksum += calculate_checksum(payload, len);
    }

    // 3. Send
    usb_write_bytes((uint8_t*)&header, sizeof(header));
    if (payload && len > 0) {
        usb_write_bytes(payload, len);
    }
    usb_write_bytes((uint8_t*)&checksum, 2);
}
```

#### 2.2.4 Command Dispatcher (`src/commands.c`)

The command dispatcher executes specific commands based on command ID.

**Command Handler Structure**:

```c
uint32_t dispatch_command(uint8_t cmd_id, uint8_t *payload, uint32_t len, 
                          uint8_t *out_payload, uint32_t *out_len) {
    switch (cmd_id) {
        case CMD_PING:
            // Echo payload back
            if (len > 0) memcpy(out_payload, payload, len);
            *out_len = len;
            return ERR_OK;

        case CMD_ALLOC:
            return handle_alloc(payload, len, out_payload, out_len);
            
        case CMD_FREE:
            return handle_free(payload, len, out_payload, out_len);
            
        case CMD_WRITE_MEM:
            return handle_write_mem(payload, len, out_payload, out_len);
            
        case CMD_READ_MEM:
            return handle_read_mem(payload, len, out_payload, out_len);
            
        case CMD_EXEC:
            return handle_exec(payload, len, out_payload, out_len);
            
        case CMD_HEAP_INFO:
            return handle_heap_info(payload, len, out_payload, out_len);

        default:
            ESP_LOGW(TAG, "Unknown command: 0x%02X", cmd_id);
            return ERR_UNKNOWN_CMD;
    }
}
```

**CMD_ALLOC Implementation**:

```c
typedef struct {
    uint32_t size;
    uint32_t caps;
    uint32_t alignment;
} cmd_alloc_req_t;

typedef struct {
    uint32_t address;
    uint32_t error_code;
} cmd_alloc_resp_t;

static uint32_t handle_alloc(uint8_t *payload, uint32_t len, 
                             uint8_t *out_payload, uint32_t *out_len) {
    if (len < sizeof(cmd_alloc_req_t)) {
        return ERR_UNKNOWN_CMD;
    }
    
    cmd_alloc_req_t *req = (cmd_alloc_req_t*)payload;
    
    ESP_LOGI(TAG, "CMD_ALLOC: Size=%lu, Caps=0x%08lX, Align=%lu", 
             req->size, req->caps, req->alignment);

    void *ptr = heap_caps_aligned_alloc(
        req->alignment, 
        req->size, 
        req->caps
    );
    
    if (ptr) {
        ESP_LOGI(TAG, "CMD_ALLOC: Success at %p", ptr);
    } else {
        ESP_LOGE(TAG, "CMD_ALLOC: Failed");
    }

    cmd_alloc_resp_t *resp = (cmd_alloc_resp_t*)out_payload;
    resp->address = (uint32_t)ptr;
    resp->error_code = (ptr != NULL) ? 0 : ERR_ALLOC_FAIL;
    
    *out_len = sizeof(cmd_alloc_resp_t);
    return ERR_OK;
}
```

**CMD_WRITE_MEM with Cache Sync**:

```c
typedef struct {
    uint32_t address;
    // data follows
} cmd_write_req_t;

static uint32_t handle_write_mem(uint8_t *payload, uint32_t len, 
                                 uint8_t *out_payload, uint32_t *out_len) {
    if (len < sizeof(cmd_write_req_t)) {
        return ERR_UNKNOWN_CMD;
    }
    
    cmd_write_req_t *req = (cmd_write_req_t*)payload;
    uint32_t data_len = len - sizeof(cmd_write_req_t);
    uint8_t *data_ptr = payload + sizeof(cmd_write_req_t);

    // Copy data to target address
    memcpy((void*)req->address, data_ptr, data_len);

    // CRITICAL: Sync Cache
    // esp_cache_msync requires cache-line aligned address and size
    #define CACHE_LINE_SIZE 128
    
    uint32_t start_addr = req->address;
    uint32_t end_addr = start_addr + data_len;
    
    // Align to cache line boundaries
    uint32_t aligned_start = start_addr & ~(CACHE_LINE_SIZE - 1);
    uint32_t aligned_end = (end_addr + CACHE_LINE_SIZE - 1) & ~(CACHE_LINE_SIZE - 1);
    uint32_t aligned_size = aligned_end - aligned_start;
    
    ESP_LOGI(TAG, "Cache Sync: Addr=0x%08lX, Len=0x%lX -> "
                  "Aligned Addr=0x%08lX, Len=0x%lX", 
             start_addr, data_len, aligned_start, aligned_size);

    // Flush D-Cache and Invalidate I-Cache
    esp_err_t err = esp_cache_msync(
        (void*)aligned_start, 
        aligned_size, 
        ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_INVALIDATE
    );
    
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Cache sync failed: 0x%x", err);
    }

    cmd_write_resp_t *resp = (cmd_write_resp_t*)out_payload;
    resp->bytes_written = data_len;
    resp->status = (err == ESP_OK) ? 0 : 1;
    
    *out_len = sizeof(cmd_write_resp_t);
    return ERR_OK;
}
```

**CMD_EXEC Implementation**:

```c
typedef struct {
    uint32_t address;
} cmd_exec_req_t;

typedef struct {
    uint32_t return_value;
} cmd_exec_resp_t;

static uint32_t handle_exec(uint8_t *payload, uint32_t len, 
                            uint8_t *out_payload, uint32_t *out_len) {
    if (len < sizeof(cmd_exec_req_t)) {
        return ERR_UNKNOWN_CMD;
    }
    
    cmd_exec_req_t *req = (cmd_exec_req_t*)payload;

    // Cast address to function pointer
    typedef int (*jit_func_t)(void);
    jit_func_t func = (jit_func_t)req->address;
    
    ESP_LOGI(TAG, "Executing at 0x%08lX", req->address);
    
    // Call function
    int ret = func();
    
    ESP_LOGI(TAG, "Returned: %d", ret);

    cmd_exec_resp_t *resp = (cmd_exec_resp_t*)out_payload;
    resp->return_value = ret;
    
    *out_len = sizeof(cmd_exec_resp_t);
    return ERR_OK;
}
```

**CMD_HEAP_INFO Implementation**:

```c
typedef struct {
    uint32_t free_spiram;
    uint32_t total_spiram;
    uint32_t free_internal;
    uint32_t total_internal;
} cmd_heap_info_resp_t;

static uint32_t handle_heap_info(uint8_t *payload, uint32_t len, 
                                 uint8_t *out_payload, uint32_t *out_len) {
    cmd_heap_info_resp_t *resp = (cmd_heap_info_resp_t*)out_payload;
    
    resp->free_spiram = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    resp->total_spiram = heap_caps_get_total_size(MALLOC_CAP_SPIRAM);
    
    resp->free_internal = heap_caps_get_free_size(MALLOC_CAP_INTERNAL);
    resp->total_internal = heap_caps_get_total_size(MALLOC_CAP_INTERNAL);
    
    ESP_LOGI(TAG, "Heap Info: SPIRAM: %lu/%lu, INT: %lu/%lu",
             resp->free_spiram, resp->total_spiram,
             resp->free_internal, resp->total_internal);
    
    *out_len = sizeof(cmd_heap_info_resp_t);
    return ERR_OK;
}
```

#### 2.2.5 USB Transport (`src/usb_transport.c`)

The USB transport layer uses TinyUSB and FreeRTOS StreamBuffers to provide reliable, high-speed communication.

![USB Data Flow](assets/usb-data-flow.png)

**Image Prompt for `assets/usb-data-flow.png`**:
```
Create a data flow diagram showing USB communication architecture from components/p4_jit/src/usb_transport.c.

COMPONENTS (boxes, top to bottom):
1. "USB Host (PC)" - top, gray box
2. "ESP32-P4 USB PHY" - hardware layer
3. "TinyUSB Driver" - yellow box, contains "CDC-ACM Interface"
4. "RX Callback (ISR Context)" - orange box, high priority
5. "StreamBuffer (FIFO)" - blue cylinder, "16 KB"
6. "Protocol Task (Task Context)" - green box, normal priority
7. "Command Dispatcher" - purple box

DATA FLOW:
RECEIVE PATH (left side, downward arrows):
- USB Host → USB PHY: "USB Packets"
- USB PHY → TinyUSB: "Interrupt"
- TinyUSB → RX Callback: "tinyusb_cdcacm_read()"
- RX Callback → StreamBuffer: "xStreamBufferSend()"
- StreamBuffer → Protocol Task: "xStreamBufferReceive()"
- Protocol Task → Command Dispatcher: "Parsed Packets"

TRANSMIT PATH (right side, upward arrows):
- Command Dispatcher → Protocol Task: "Response Data"
- Protocol Task → TinyUSB: "tinyusb_cdcacm_write_queue()"
- TinyUSB → USB PHY: "USB Packets"
- USB PHY → USB Host: "Response"

ANNOTATIONS:
- RX Callback: "High Priority ISR"
- StreamBuffer: "Decouples ISR from Task"
- Protocol Task: "Blocking Read/Write"
- Add note: "DMA Transfer" on USB PHY
- Add note: "No data loss" on StreamBuffer

Use professional technical diagram style with clear data flow arrows.
Reference: usb_transport_init(), rx_callback(), usb_read_bytes(), usb_write_bytes()
```

**Initialization**:

```c
static StreamBufferHandle_t rx_stream_buffer = NULL;
static uint8_t rx_temp_buf[2048];

void usb_transport_init(void) {
    ESP_LOGI(TAG, "Initializing USB Transport...");

    // 1. Create Stream Buffer (16KB default)
    rx_stream_buffer = xStreamBufferCreate(
        CONFIG_P4_JIT_STREAM_BUFFER_SIZE, 
        1  // Trigger level (1 byte)
    );
    
    if (rx_stream_buffer == NULL) {
        ESP_LOGE(TAG, "Failed to create stream buffer");
        abort();
    }

    // 2. Install TinyUSB Driver
    const tinyusb_config_t tusb_cfg = {
        .port = TINYUSB_PORT_HIGH_SPEED_0, 
        .task = {
            .size = 4096,
            .priority = 5,
            .xCoreID = 0,
        },
    };
    ESP_ERROR_CHECK(tinyusb_driver_install(&tusb_cfg));

    // 3. Initialize CDC-ACM
    tinyusb_config_cdcacm_t acm_cfg = {
        .cdc_port = TINYUSB_CDC_ACM_0,
        .callback_rx = &rx_callback,
        .callback_rx_wanted_char = NULL,
        .callback_line_state_changed = NULL,
        .callback_line_coding_changed = NULL
    };
    ESP_ERROR_CHECK(tinyusb_cdcacm_init(&acm_cfg));

    ESP_LOGI(TAG, "USB Initialized");
}
```

**RX Callback (ISR Context)**:

```c
static void rx_callback(int itf, cdcacm_event_t *event) {
    size_t rx_size = 0;
    
    // Read from TinyUSB internal buffer
    esp_err_t ret = tinyusb_cdcacm_read(
        itf, 
        rx_temp_buf, 
        sizeof(rx_temp_buf), 
        &rx_size
    );
    
    if (ret == ESP_OK && rx_size > 0) {
        // Send to StreamBuffer (non-blocking)
        size_t sent = xStreamBufferSend(
            rx_stream_buffer, 
            rx_temp_buf, 
            rx_size, 
            0  // No wait (ISR context)
        );
        
        if (sent != rx_size) {
            ESP_LOGW(TAG, "StreamBuffer overflow, dropped %d bytes", 
                     rx_size - sent);
        }
    }
}
```

**Blocking Read (Task Context)**:

```c
void usb_read_bytes(uint8_t *buffer, size_t len) {
    size_t received = 0;
    
    while (received < len) {
        // Block until at least 1 byte available
        size_t chunk = xStreamBufferReceive(
            rx_stream_buffer, 
            buffer + received, 
            len - received, 
            portMAX_DELAY  // Wait forever
        );
        
        received += chunk;
    }
}
```

**Blocking Write (Task Context)**:

```c
void usb_write_bytes(const uint8_t *buffer, size_t len) {
    size_t sent = 0;
    
    while (sent < len) {
        size_t remaining = len - sent;
        
        // Queue data for transmission
        size_t queued = tinyusb_cdcacm_write_queue(
            TINYUSB_CDC_ACM_0, 
            buffer + sent, 
            remaining
        );
        
        if (queued > 0) {
            // Flush to USB
            tinyusb_cdcacm_write_flush(TINYUSB_CDC_ACM_0, 0);
            sent += queued;
        } else {
            // Buffer full, wait briefly
            vTaskDelay(pdMS_TO_TICKS(1));
        }
    }
    
    // Final flush
    tinyusb_cdcacm_write_flush(TINYUSB_CDC_ACM_0, 0);
}
```

### 2.3 Runtime System (`host/p4jit/runtime/`)

The runtime system provides the Python API for interacting with the device.

#### 2.3.1 P4JIT Manager (`p4jit.py`)

The P4JIT class is the main entry point for users.

```python
class P4JIT:
    """
    The Manager class for P4-JIT operations.
    Aggregates Toolchain and Runtime layers.
    """
    
    def __init__(self, port: str = None, config_path: str = 'config/toolchain.yaml'):
        """Initialize JIT system and connect to device."""
        logger.info("Initializing P4JIT System...")
        
        self.session = JITSession()
        self.session.connect(port)  # Auto-detect if None
        
        self.builder = Builder()
        
        logger.info("P4JIT Initialized.")
    
    def load(self, 
             source: str, 
             function_name: str,
             base_address: int = 0x03000004,
             arg_address: int = 0x00030004,
             optimization: str = 'O3',
             output_dir: Optional[str] = None,
             use_firmware_elf: bool = True,
             code_caps: int = MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT,
             data_caps: int = MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT,
             alignment: int = 16,
             smart_args: bool = True) -> JITFunction:
        """
        Build, allocate, and load a function.
        Returns a callable JITFunction object.
        """
        
        logger.info(f"Loading '{function_name}' from '{os.path.basename(source)}'...")
        
        # 1. Pass 1: Build with dummy addresses for size measurement
        logger.log(INFO_VERBOSE, f"Pass 1: Preliminary Build")
        
        temp_bin = self.builder.wrapper.build_with_wrapper(
            source=source,
            function_name=function_name,
            base_address=base_address,
            arg_address=arg_address,
            output_dir=output_dir,
            use_firmware_elf=use_firmware_elf
        )
        
        # 2. Allocate device memory
        logger.log(INFO_VERBOSE, f"Allocating device memory")
        
        alloc_code_size = temp_bin.total_size + 64
        alloc_args_size = temp_bin.metadata['addresses']['args_array_bytes']
        
        real_code_addr = self.session.device.allocate(
            alloc_code_size, code_caps, alignment
        )
        real_args_addr = self.session.device.allocate(
            alloc_args_size, data_caps, alignment
        )
        
        logger.info(f"  Code: 0x{real_code_addr:08X} ({alloc_code_size} bytes)")
        logger.info(f"  Args: 0x{real_args_addr:08X} ({alloc_args_size} bytes)")
        
        # 3. Pass 2: Rebuild with real addresses
        logger.log(INFO_VERBOSE, "Pass 2: Re-linking with allocated addresses")
        
        final_bin = self.builder.wrapper.build_with_wrapper(
            source=source,
            function_name=function_name,
            base_address=real_code_addr,
            arg_address=real_args_addr,
            output_dir=output_dir,
            use_firmware_elf=use_firmware_elf
        )
        
        # 4. Upload binary
        logger.log(INFO_VERBOSE, "Uploading binary to device")
        self.session.device.write_memory(real_code_addr, final_bin.data)
        
        # 5. Create function wrapper
        logger.info("Function loaded successfully")
        return JITFunction(
            self.session,
            final_bin,
            real_code_addr,
            real_args_addr,
            smart_args
        )
    
    def get_heap_stats(self, print_s: bool = True) -> Dict[str, int]:
        """Get heap statistics from device."""
        stats = self.session.device.get_heap_info()
        
        if print_s:
            logger.info("[Heap Statistics]")
            for k, v in stats.items():
                logger.info(f"  {k:<15}: {v:>10} bytes ({v/1024:>6.2f} KB)")
        
        return stats
```

**JITFunction Class**:

```python
class JITFunction:
    """
    Represents a specific compiled and loaded function.
    Provides a callable interface and resource management.
    """
    
    def __init__(self, session, binary, code_addr, args_addr, smart_args):
        self.session = session
        self.binary = binary
        self.code_addr = code_addr
        self.args_addr = args_addr
        self.smart_args = smart_args
        self.valid = True
        
        # Create persistent RemoteFunction wrapper
        from .runtime.remote_function import RemoteFunction
        
        signature = None
        if self.smart_args and self.binary.metadata:
            signature = self.binary.metadata
        
        self.remote_func = RemoteFunction(
            self.session.device,
            self.code_addr,
            self.args_addr,
            signature=signature,
            smart_args=self.smart_args
        )
    
    @property
    def sync_arrays(self):
        """Get/set automatic array synchronization."""
        return self.remote_func.sync_enabled
    
    @sync_arrays.setter
    def sync_arrays(self, value: bool):
        self.remote_func.sync_enabled = value
    
    def __call__(self, *args) -> Any:
        """Execute the function."""
        if not self.valid:
            raise RuntimeError("JITFunction has been freed")
        
        return self.remote_func(*args)
    
    def free(self):
        """Release device resources."""
        if not self.valid:
            return
        
        try:
            self.session.device.free(self.code_addr)
            self.session.device.free(self.args_addr)
        except Exception as e:
            logger.warning(f"Failed to free resources: {e}")
        
        self.valid = False
```

#### 2.3.2 JIT Session (`jit_session.py`)

The JITSession manages the connection and device discovery.

```python
class JITSession:
    """Orchestrates the JIT session."""
    
    def __init__(self):
        self.device = DeviceManager()
    
    def connect(self, port: str = None):
        """
        Connect to device.
        Auto-detects port if not specified.
        """
        if port:
            self.device.port = port
            logger.info(f"Connecting to {port}")
            self.device.connect()
            
            if not self.device.ping():
                self.device.disconnect()
                raise RuntimeError(f"Device at {port} did not respond to PING")
        else:
            logger.info("Auto-detecting JIT device...")
            found = False
            ports = list(serial.tools.list_ports.comports())
            
            for p in ports:
                try:
                    logger.debug(f"Probing {p.device}...")
                    self.device.port = p.device
                    self.device.connect()
                    
                    if self.device.ping():
                        found = True
                        logger.info(f"Found JIT Device at {p.device}")
                        break
                    
                    self.device.disconnect()
                except Exception as e:
                    logger.debug(f"Probe failed: {e}")
            
            if not found:
                raise RuntimeError("Could not find JIT Device")
    
    def load_function(self, binary_object, args_addr, smart_args=False):
        """Load function and return callable wrapper."""
        logger.log(INFO_VERBOSE, 
                   f"Uploading code to 0x{binary_object.base_address:08X}")
        
        self.device.write_memory(
            binary_object.base_address, 
            binary_object.data
        )
        
        signature = None
        if smart_args and binary_object.metadata:
            signature = binary_object.metadata
        
        return RemoteFunction(
            self.device, 
            binary_object.entry_address, 
            args_addr,
            signature=signature, 
            smart_args=smart_args
        )
```

#### 2.3.3 Device Manager (`device_manager.py`)

The DeviceManager implements the binary protocol and maintains the shadow allocation table.

```python
class DeviceManager:
    """Handles low-level device communication."""
    
    def __init__(self, port: str = None, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        
        # Shadow allocation table
        self.allocations: Dict[int, dict] = {}
    
    def _send_packet(self, cmd_id: int, payload: bytes) -> bytes:
        """Send packet and receive response."""
        if not self.serial or not self.serial.is_open:
            raise RuntimeError("Device not connected")
        
        # 1. Construct header
        header = struct.pack('<2sBBI', MAGIC, cmd_id, 0x00, len(payload))
        
        # 2. Calculate checksum
        checksum = sum(header)
        if payload:
            checksum += sum(payload)
        checksum &= 0xFFFF
        
        # 3. Send
        self.serial.write(header)
        if payload:
            self.serial.write(payload)
        self.serial.write(struct.pack('<H', checksum))
        
        # 4. Receive response
        magic = self.serial.read(2)
        if magic != MAGIC:
            raise RuntimeError(f"Invalid response magic: {magic.hex()}")
        
        resp_header_data = self.serial.read(6)
        resp_cmd, resp_flags, resp_len = struct.unpack('<BBI', resp_header_data)
        
        resp_payload = b''
        if resp_len > 0:
            resp_payload = self.serial.read(resp_len)
        
        resp_checksum = struct.unpack('<H', self.serial.read(2))[0]
        
        # Check error flag
        if resp_flags == 0x02:
            err_code = struct.unpack('<I', resp_payload)[0] if resp_payload else -1
            raise RuntimeError(f"Device error: {err_code}")
        
        return resp_payload
    
    def allocate(self, size: int, caps: int, alignment: int) -> int:
        """Allocate device memory."""
        payload = struct.pack('<III', size, caps, alignment)
        
        logger.log(INFO_VERBOSE, 
                   f"Allocating {size} bytes (caps={caps:08x}, align={alignment})")
        
        resp = self._send_packet(CMD_ALLOC, payload)
        
        addr, err = struct.unpack('<II', resp)
        
        if err != 0:
            logger.error(f"Allocation failed: size={size}")
            raise MemoryError(f"Allocation failed: error={err}")
        
        # Track in shadow table
        self.allocations[addr] = {
            'size': size,
            'caps': caps,
            'align': alignment
        }
        
        logger.debug(f"Allocated {size} bytes at 0x{addr:08X}")
        return addr
    
    def write_memory(self, address: int, data: bytes):
        """Write to device memory with bounds checking."""
        end_addr = address + len(data)
        
        # Validate against shadow table
        valid = False
        for start, info in self.allocations.items():
            alloc_end = start + info['size']
            if start <= address and end_addr <= alloc_end:
                valid = True
                break
        
        if not valid:
            logger.error(f"Segmentation Fault: Write to 0x{address:08X}")
            raise PermissionError(f"Segmentation Fault: 0x{address:08X} out of bounds")
        
        logger.log(INFO_VERBOSE, f"Writing {len(data)} bytes to 0x{address:08X}")
        
        payload = struct.pack('<I', address) + data
        self._send_packet(CMD_WRITE_MEM, payload)
    
    def execute(self, address: int) -> int:
        """Execute code at address."""
        logger.log(INFO_VERBOSE, f"Executing at 0x{address:08X}")
        
        payload = struct.pack('<I', address)
        resp = self._send_packet(CMD_EXEC, payload)
        
        ret_val = struct.unpack('<I', resp)[0]
        logger.debug(f"Execution finished. Return: {ret_val}")
        
        return ret_val
    
    def get_heap_info(self) -> Dict[str, int]:
        """Get heap statistics."""
        resp = self._send_packet(CMD_HEAP_INFO, b'')
        
        free_spiram, total_spiram, free_internal, total_internal = \
            struct.unpack('<IIII', resp)
        
        return {
            'free_spiram': free_spiram,
            'total_spiram': total_spiram,
            'free_internal': free_internal,
            'total_internal': total_internal
        }
```

#### 2.3.4 Remote Function (`remote_function.py`)

The RemoteFunction wraps the execution logic.

```python
class RemoteFunction:
    """Callable wrapper for device functions."""
    
    def __init__(self, device_manager, code_addr, args_addr, 
                 signature=None, smart_args=False, sync_arrays=True):
        self.dm = device_manager
        self.code_addr = code_addr
        self.args_addr = args_addr
        self.signature = signature
        self.smart_args = smart_args
        self.sync_enabled = sync_arrays
    
    def __call__(self, *args) -> Any:
        """Call the remote function."""
        logger.debug(f"Calling function at 0x{self.code_addr:08X}")
        
        if self.smart_args:
            if not self.signature:
                raise ValueError("Smart args enabled but no signature")
            
            # Create fresh handler
            handler = SmartArgs(
                self.dm, 
                self.signature, 
                sync_enabled=self.sync_enabled
            )
            
            try:
                # Pack arguments
                args_blob = handler.pack(*args)
                
                # Write to device
                self.dm.write_memory(self.args_addr, args_blob)
                
                # Execute
                self.dm.execute(self.code_addr)
                
                # Sync back modified arrays
                handler.sync_back()
                
                # Read return value
                return handler.get_return_value(self.args_addr)
            finally:
                handler.cleanup()
        else:
            # Legacy mode
            if len(args) != 1 or not isinstance(args[0], bytes):
                raise ValueError("Legacy mode expects single bytes argument")
            
            args_blob = args[0]
            
            self.dm.write_memory(self.args_addr, args_blob)
            result = self.dm.execute(self.code_addr)
            
            return result
```

#### 2.3.5 Smart Args (`smart_args.py`)

Smart Args handles automatic type conversion and memory management.

![Smart Args Flow](assets/smart-args-flow.png)

**Image Prompt for `assets/smart-args-flow.png`**:
```
Generate a sequence diagram showing Smart Args execution flow from host/p4jit/runtime/smart_args.py.

ACTORS (left to right):
1. "User Code" (stick figure)
2. "SmartArgs Handler" (box)
3. "DeviceManager" (box)
4. "ESP32-P4 Device" (box)

SEQUENCE OF EVENTS (top to bottom with arrows):

1. User Code → SmartArgs: "func(array, scalar)"
2. SmartArgs → SmartArgs: "Validate types against signature"
3. SmartArgs → SmartArgs: "For each array: allocate device memory"
4. SmartArgs → DeviceManager: "allocate(size, caps, align)"
5. DeviceManager → ESP32-P4: "CMD_ALLOC"
6. ESP32-P4 → DeviceManager: "address"
7. DeviceManager → SmartArgs: "address"
8. SmartArgs → SmartArgs: "Pack args to binary (struct.pack)"
9. SmartArgs → DeviceManager: "write_memory(args_addr, blob)"
10. DeviceManager → ESP32-P4: "CMD_WRITE_MEM"
11. SmartArgs → DeviceManager: "execute(code_addr)"
12. DeviceManager → ESP32-P4: "CMD_EXEC"
13. ESP32-P4: Internal box "Function executes, modifies arrays"
14. ESP32-P4 → DeviceManager: "return value (in args buffer)"
15. SmartArgs → SmartArgs: "Read return value from slot 31"
16. SmartArgs → SmartArgs: "If sync_enabled: read modified arrays"
17. SmartArgs → DeviceManager: "read_memory(array_addr, size)" [in loop]
18. DeviceManager → ESP32-P4: "CMD_READ_MEM" [in loop]
19. ESP32-P4 → DeviceManager: "array data" [in loop]
20. SmartArgs → SmartArgs: "np.copyto(original_array, new_data)"
21. SmartArgs → DeviceManager: "free(array_addr)" [for each array]
22. DeviceManager → ESP32-P4: "CMD_FREE" [for each]
23. SmartArgs → User Code: "return result"

Add annotations:
- "Type validation" at step 2
- "Automatic allocation" at steps 4-7
- "Binary packing" at step 8
- "Bidirectional sync" at steps 16-20
- "Cleanup" at steps 21-22

Use standard UML sequence diagram notation with lifelines and activation boxes.
Reference: smart_args.py:pack(), sync_back(), get_return_value(), cleanup()
```

**Complete Implementation**:

```python
class SmartArgs:
    """Handles automatic argument processing."""
    
    def __init__(self, device_manager, signature, sync_enabled=True):
        self.dm = device_manager
        self.signature = signature
        self.sync_enabled = sync_enabled
        
        self.allocations = []
        self.tracked_arrays = []
        
        self._load_config()
    
    def pack(self, *args) -> bytes:
        """Process arguments and pack into binary blob."""
        parameters = self.signature['parameters']
        
        if len(args) != len(parameters):
            raise ValueError(
                f"Expected {len(parameters)} arguments, got {len(args)}"
            )
        
        packed_args = []
        
        for i, (arg, param) in enumerate(zip(args, parameters)):
            param_type = param['type']
            category = param['category']
            
            logger.log(INFO_VERBOSE, 
                       f"Arg {i} ({param['name']}): {param_type}, {category}")
            
            if category == 'pointer':
                packed_val = self._handle_pointer(arg, param_type)
            else:
                packed_val = self._handle_value(arg, param_type)
            
            packed_args.append(packed_val)
        
        return b''.join(packed_args)
    
    def _handle_pointer(self, arg, param_type):
        """Handle pointer arguments (NumPy arrays)."""
        if not isinstance(arg, np.ndarray):
            raise TypeError(f"Expected NumPy array, got {type(arg)}")
        
        # Flatten array
        flat_arr = arg.ravel()
        
        # Allocate device memory
        size_bytes = flat_arr.nbytes
        addr = self.dm.allocate(
            size_bytes, 
            MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT, 
            16
        )
        self.allocations.append(addr)
        
        # Write data
        self.dm.write_memory(addr, flat_arr.tobytes())
        
        # Track for sync-back
        if self.sync_enabled:
            self.tracked_arrays.append({
                'addr': addr,
                'array': arg,
                'size': size_bytes,
                'shape': arg.shape,
                'dtype': arg.dtype
            })
        
        # Return address as uint32
        return struct.pack('<I', addr)
    
    def _handle_value(self, arg, param_type):
        """Handle scalar value arguments."""
        if 'float' in param_type:
            return struct.pack('<f', float(arg))
        else:
            return struct.pack('<i', int(arg))
    
    def get_return_value(self, args_addr):
        """Read and convert return value from slot 31."""
        return_type = self.signature['return_type']
        
        if return_type == 'void':
            return None
        
        # Read last slot (offset 124)
        raw_bytes = self.dm.read_memory(args_addr + 124, 4)
        
        if '*' in return_type:
            val = struct.unpack('<I', raw_bytes)[0]
            return np.uint32(val)
        elif 'float' in return_type or 'double' in return_type:
            val = struct.unpack('<f', raw_bytes)[0]
            return np.float32(val)
        else:
            val_i32 = struct.unpack('<i', raw_bytes)[0]
            dtype_str = self.reverse_type_map.get(return_type, 'int32')
            return np.dtype(dtype_str).type(val_i32)
    
    def sync_back(self):
        """Read modified arrays back from device."""
        if not self.sync_enabled or not self.tracked_arrays:
            return
        
        for item in self.tracked_arrays:
            try:
                logger.log(INFO_VERBOSE, 
                           f"Syncing array from 0x{item['addr']:08X}")
                
                raw_bytes = self.dm.read_memory(item['addr'], item['size'])
                new_data = np.frombuffer(
                    raw_bytes, 
                    dtype=item['dtype']
                ).reshape(item['shape'])
                
                np.copyto(item['array'], new_data)
            except Exception as e:
                logger.warning(f"Failed to sync array: {e}")
    
    def cleanup(self):
        """Free all allocated memory."""
        for addr in self.allocations:
            try:
                self.dm.free(addr)
            except Exception as e:
                logger.warning(f"Failed to free 0x{addr:08x}: {e}")
        
        self.allocations.clear()
        self.tracked_arrays.clear()
```

---

## 3. Build System Deep Dive

### 3.1 Multi-File Compilation

#### 3.1.1 File Discovery Algorithm

The builder automatically discovers all compilable source files in the same directory as the entry file.

**Process**:
1. Extract directory from entry file path
2. Iterate through configured extensions
3. Use `glob` to find matching files
4. Sort alphabetically for deterministic builds

**Example**:

If entry file is `project/src/main.c`, the builder searches for:
- `project/src/*.c`
- `project/src/*.cpp`
- `project/src/*.cc`
- `project/src/*.cxx`
- `project/src/*.S`

**Code**:
```python
def _discover_source_files(self, source_dir):
    compile_extensions = self.config['extensions']['compile'].keys()
    discovered_files = []
    
    for ext in compile_extensions:
        pattern = os.path.join(source_dir, f'*{ext}')
        found = glob.glob(pattern)
        discovered_files.extend(found)
    
    discovered_files.sort()  # Deterministic order
    return discovered_files
```

#### 3.1.2 Supported File Types

| Extension | Compiler | Language | Notes |
|-----------|----------|----------|-------|
| `.c` | gcc | C | Standard C source |
| `.cpp` | g++ | C++ | C++ source |
| `.cc` | g++ | C++ | Alternative C++ extension |
| `.cxx` | g++ | C++ | Alternative C++ extension |
| `.S` | gcc | Assembly | With C preprocessor |
| `.h`, `.hpp` | N/A | Headers | Not compiled directly |

#### 3.1.3 Compilation Strategy

**Per-File Compilation**:
```
main.c    → gcc → main.o
helper.c  → gcc → helper.o
utils.cpp → g++ → utils.o
```

**Single Linking Step**:
```
main.o + helper.o + utils.o → ld → output.elf
```

**Benefits**:
- Parallel compilation possible (not implemented yet)
- Incremental builds possible (not implemented yet)
- Clear separation of concerns

#### 3.1.4 Link-Time Optimization (LTO)

When enabled via `config/toolchain.yaml`:

```yaml
compiler:
  flags:
    - "-flto"
linker:
  flags:
    - "-flto"
```

**How LTO Works**:
1. Compiler generates intermediate representation (IR) instead of pure object code
2. Linker sees all IR from all object files
3. Linker performs global optimizations:
   - Cross-module inlining
   - Dead code elimination across modules
   - Constant propagation across modules
4. Final machine code generated with full visibility

**Example**:

Without LTO:
```c
// helper.c
static inline int square(int x) { return x * x; }

// main.c
extern int square(int x);
int compute(int a) { return square(a); }
// Result: Function call overhead
```

With LTO:
```c
// After LTO
int compute(int a) { return a * a; }
// Result: Fully inlined, no function call
```

### 3.2 Two-Pass Linking System

The two-pass system is fundamental to how P4-JIT works.

![Two-Pass Linking](assets/two-pass-linking.png)

**Image Prompt for `assets/two-pass-linking.png`**:
```
Create a flowchart illustrating the two-pass linking process.

SPLIT INTO TWO PARALLEL SECTIONS:

LEFT SECTION - Pass 1 (Probe):
1. START: "Entry Source File (main.c)" [rounded rectangle]
2. PROCESS: "Compile with Dummy Address" [rectangle]
   - Annotation: "Base = 0x03000004"
   - Annotation: "Args = 0x00030004"
3. PROCESS: "Link with Dummy Linker Script" [rectangle]
4. PROCESS: "Extract Binary" [rectangle]
5. PROCESS: "Measure Size" [rectangle]
   - Show output: "Code Size = 2048 bytes"
   - Show output: "Args Size = 128 bytes"
6. END: "Size Information" [rounded rectangle, blue]

RIGHT SECTION - Pass 2 (Final):
1. START: "Size Information" [rounded rectangle, blue] (arrow from Pass 1)
2. PROCESS: "Allocate Device Memory" [rectangle]
   - Show: "CMD_ALLOC(2048 + 64) → 0x40800000"
   - Show: "CMD_ALLOC(128) → 0x48200000"
3. PROCESS: "Re-compile Same Source" [rectangle]
   - Annotation: "Base = 0x40800000 (real)"
   - Annotation: "Args = 0x48200000 (real)"
4. PROCESS: "Link with Real Addresses" [rectangle]
5. PROCESS: "Extract Binary" [rectangle]
6. PROCESS: "Upload to Device" [rectangle]
   - Show: "CMD_WRITE_MEM(0x40800000, binary)"
7. END: "Ready to Execute" [rounded rectangle, green]

CONNECTING ARROW:
- Large arrow from Pass 1 "Size Information" to Pass 2 START
- Label: "Memory Requirements"

COLOR CODING:
- Pass 1 boxes: Light orange (probe/temporary)
- Pass 2 boxes: Light green (final/permanent)
- Data transfer: Blue arrows

ANNOTATIONS:
- Pass 1: "Addresses INVALID for execution"
- Pass 2: "Addresses VALID, code executable"
- Between passes: "Same source code, different addresses"

Reference: builder.py:build() and p4jit.py:load()
Use professional flowchart style with clear visual separation.
```

#### 3.2.1 Why Two Passes?

**The Problem**:
- Position-specific code requires knowing the target address at link time
- We cannot know the address until we allocate memory
- We cannot allocate memory without knowing the size
- We cannot know the size until we compile

**The Solution**:
- Pass 1: Compile with dummy address to measure size
- Allocate memory based on measured size
- Pass 2: Recompile with real address

#### 3.2.2 Pass 1: Probe Build

**Purpose**: Measure binary size

**Process**:
```python
# 1. Compile with dummy addresses
temp_bin = builder.wrapper.build_with_wrapper(
    source='main.c',
    function_name='compute',
    base_address=0x03000004,  # Dummy
    arg_address=0x00030004    # Dummy
)

# 2. Extract size information
code_size = temp_bin.total_size
args_size = temp_bin.metadata['addresses']['args_array_bytes']
```

**Characteristics**:
- Binary is syntactically correct
- Addresses are semantically invalid
- Cannot be executed
- Used only for size measurement

#### 3.2.3 Pass 2: Final Build

**Purpose**: Create executable binary

**Process**:
```python
# 1. Allocate device memory using measured sizes
real_code_addr = device.allocate(code_size + 64, caps, alignment)
real_args_addr = device.allocate(args_size, caps, alignment)

# 2. Recompile with real addresses
final_bin = builder.wrapper.build_with_wrapper(
    source='main.c',  # Same source!
    function_name='compute',
    base_address=real_code_addr,  # Real address
    arg_address=real_args_addr    # Real address
)

# 3. Upload and execute
device.write_memory(real_code_addr, final_bin.data)
device.execute(real_code_addr)
```

**Characteristics**:
- Binary is fully valid
- All addresses correct
- Ready for execution
- Matches allocated memory layout

#### 3.2.4 Deterministic Builds

**Critical Property**: Same source + same addresses = bit-identical binary

**Why It Matters**:
- Enables caching (future feature)
- Reproducible builds
- Debugging reliability

**Enforced By**:
- Sorted file list (deterministic discovery)
- Fixed compiler flags
- No timestamps in binary

### 3.3 Symbol Bridge (Firmware ELF Linking)

The Symbol Bridge enables JIT code to call functions from the base firmware.

#### 3.3.1 Concept

Instead of re-implementing standard library functions, we resolve symbols against the firmware's symbol table at link time.

**Example**:

JIT Code:
```c
#include <stdio.h>

int test_print(void) {
    printf("Hello from JIT!\n");
    return 42;
}
```

Without Symbol Bridge:
- Linker error: "undefined reference to 'printf'"

With Symbol Bridge:
- Linker reads `firmware.elf` symbol table
- Finds `printf` at address `0x400167a6`
- Resolves reference to absolute address
- JIT code calls firmware's `printf` directly

#### 3.3.2 Configuration

In `config/toolchain.yaml`:

```yaml
linker:
  firmware_elf: "firmware/build/p4_jit_firmware.elf"
```

**Path Resolution**:
- Relative to project root
- Must exist when `use_firmware_elf=True`

#### 3.3.3 Linker Flag: `-Wl,-R,<firmware.elf>`

**GCC Linker Option**:
```bash
riscv32-esp-elf-gcc ... -Wl,-R,firmware.elf ...
```

**What It Does**:
- `-Wl,`: Pass option to linker
- `-R <file>`: Read symbol table from ELF file
- Resolves undefined symbols against this table
- Generates absolute address references

**Important**: This is **not** dynamic linking. Addresses are resolved at compile time, not runtime.

#### 3.3.4 Available Symbols

**Standard C Library**:
- `printf`, `sprintf`, `snprintf`, `vprintf`
- `malloc`, `free`, `calloc`, `realloc`
- `memcpy`, `memset`, `memmove`, `memcmp`
- `strcmp`, `strcpy`, `strlen`, `strcat`

**ESP-IDF Functions**:
- `esp_log_write`
- `esp_timer_get_time`
- `esp_random`
- `heap_caps_malloc`, `heap_caps_free`

**FreeRTOS**:
- `vTaskDelay`
- `xTaskCreate`
- `xSemaphoreCreateMutex`

**Hardware Access**:
- GPIO functions
- I2C/SPI drivers
- ADC/DAC functions

**Verification**:

To see available symbols:
```bash
riscv32-esp-elf-nm firmware.elf | grep " T "
```

#### 3.3.5 Limitations

1. **Firmware Must Be Built First**: Cannot resolve symbols from non-existent ELF
2. **Symbol Must Exist**: Linker fails if symbol not found in firmware
3. **ABI Compatibility**: Firmware and JIT code must use same calling convention
4. **No Weak Symbols**: Cannot override firmware functions from JIT code

#### 3.3.6 Use Case: Dynamic Debugging

```c
#include <esp_log.h>

void debug_function(int value) {
    ESP_LOGI("JIT", "Debug value: %d", value);
}
```

This calls firmware's `ESP_LOGI` macro, which expands to `esp_log_write`.

---

## 4. Wrapper System

### 4.1 The ABI Problem

#### 4.1.1 RISC-V Calling Convention (ILP32F)

**Register Usage**:

| Registers | Purpose | Caller/Callee Saved |
|-----------|---------|---------------------|
| `a0-a7` | Integer arguments & return | Caller-saved |
| `fa0-fa7` | Float arguments & return | Caller-saved |
| `sp` | Stack pointer | Callee-saved |
| `ra` | Return address | Caller-saved |
| `s0-s11` | Saved registers | Callee-saved |
| `t0-t6` | Temporary registers | Caller-saved |

**Argument Passing**:
- First 8 integer/pointer arguments in `a0-a7`
- First 8 float arguments in `fa0-fa7`
- Additional arguments on stack
- Small structs (<= 16 bytes) passed in registers

**Return Values**:
- Integer/pointer in `a0`
- Float in `fa0`
- Large structs via hidden pointer (first argument)

#### 4.1.2 Remote Execution Challenge

**Problem**: Python on host PC cannot directly manipulate RISC-V registers on remote device

**Why Not Just Call**:
```python
# This is impossible
device.set_register('a0', 10)
device.set_register('a1', 20)
device.call_function(address)
```

**Reasons**:
- No remote register access protocol
- CPU registers are CPU-internal
- Would require custom hardware/debugger interface

### 4.2 Memory-Mapped I/O Solution

#### 4.2.1 Args Buffer Structure

**Concept**: Use shared memory as communication channel

**Layout**:
```
Address: arg_address
+--------+--------+--------+--------+
| Slot 0 | Slot 1 | Slot 2 | Slot 3 |  <- Arguments
+--------+--------+--------+--------+
|   ...  |   ...  |   ...  |   ...  |
+--------+--------+--------+--------+
| Slot28 | Slot29 | Slot30 | Slot31 |
+--------+--------+--------+--------+
                           ↑
                    Return Value (124 bytes offset)
```

Each slot = 4 bytes = 32 bits

**Total Size**: 32 slots × 4 bytes = 128 bytes

#### 4.2.2 Data Flow

**Write Arguments** (Host):
```python
io[0] = pointer_address
io[1] = int32_value
io[2] = float32_bits_as_int
```

**Read Arguments** (Device Wrapper):
```c
volatile int32_t *io = (volatile int32_t *)arg_address;
Type* ptr = (Type*)io[0];
int32_t val = *(int32_t*)&io[1];
float f = *(float*)&io[2];
```

**Write Return** (Device Wrapper):
```c
*(float*)&io[31] = result;
```

**Read Return** (Host):
```python
result_bytes = device.read_memory(arg_address + 124, 4)
result = struct.unpack('<f', result_bytes)[0]
```

### 4.3 Complete Wrapper Example

**Source Function**:
```c
// geometry.c
typedef struct { float x; int y; } Point;

float sum_point(Point* p, int8_t z, uint16_t* arr) {
    return p->x + (float)p->y + (float)z + (float)arr[0];
}
```

**Generated Wrapper** (temp.c):
```c
#include 
#include "geometry.h"

typedef int esp_err_t;
#define ESP_OK 0

esp_err_t call_remote(void) {
    volatile int32_t *io = (volatile int32_t *)0x48211640;

    // Argument 0: POINTER type Point*
    Point* p = (Point*) io[0];

    // Argument 1: VALUE type int8_t
    int8_t z = *(int8_t*)& io[1];

    // Argument 2: POINTER type uint16_t*
    uint16_t* arr = (uint16_t*) io[2];

    // Call original function
    float result = sum_point(p, z, arr);

    // Write result (float) to slot 31
    *(float*)&io[31] = result;

    return ESP_OK;
}
```

---

## 5. Memory Management

### 5.1 ESP32-P4 Memory Regions

![ESP32-P4 Memory Map](assets/esp32p4-memory-map.png)

**Image Prompt for `assets/esp32p4-memory-map.png`**:
```
Generate a memory map diagram for ESP32-P4 showing physical address ranges.

VERTICAL BAR LAYOUT (Address space 0x00000000 to 0xFFFFFFFF):

REGIONS FROM TOP TO BOTTOM:
1. "ROM" 
   - Address: 0x40000000 - 0x40100000
   - Size: 1 MB
   - Color: Light gray
   - Label: "Boot ROM"

2. "IRAM"
   - Address: 0x40800000 - 0x40880000
   - Size: 512 KB
   - Color: Green
   - Label: "Instruction RAM (Executable)"

3. "DRAM"
   - Address: 0x3FC00000 - 0x3FD00000
   - Size: 1 MB
   - Color: Blue
   - Label: "Data RAM"

4. "L2MEM/SRAM"
   - Address: 0x4FF00000 - 0x4FFBFFFF
   - Size: 768 KB
   - Color: Yellow
   - Label: "Internal SRAM\n(Requires PMP_IDRAM_SPLIT=n)"

5. "PSRAM"
   - Address: 0x30100000 - 0x32100000
   - Size: 32 MB
   - Color: Purple
   - Label: "External PSRAM\n(Cached, Execute-In-Place)"

6. "Memory-Mapped Peripherals"
   - Address: 0x50000000 - 0x60000000
   - Color: Orange
   - Label: "I/O, GPIO, SPI, I2C, etc."

ANNOTATIONS:
- Add arrow to PSRAM: "Typical JIT Code Location"
- Add arrow to L2MEM: "Optional: Low-latency code"
- Add legend:
  - Green: "Executable"
  - Blue: "Data Only"
  - Yellow: "Configurable (RWX)"
  - Purple: "Cached External"

Add performance notes:
- IRAM: "Fast, Direct"
- DRAM: "Fast, Direct"
- L2MEM: "Fast, Direct (if enabled)"
- PSRAM: "Slower, but cached"

Use professional technical diagram style with clear address labels.
```

### 5.2 Memory Capabilities

**ESP-IDF Heap Capabilities** (from `runtime/memory_caps.py`):

```python
MALLOC_CAP_EXEC      = (1<<0)   # Executable
MALLOC_CAP_32BIT     = (1<<1)   # 32-bit aligned access
MALLOC_CAP_8BIT      = (1<<2)   # Byte-addressable
MALLOC_CAP_DMA       = (1<<3)   # DMA-capable
MALLOC_CAP_SPIRAM    = (1<<10)  # External PSRAM
MALLOC_CAP_INTERNAL  = (1<<11)  # Internal SRAM
MALLOC_CAP_DEFAULT   = (1<<12)  # Default region
```

**Common Combinations**:

| Use Case | Caps | Notes |
|----------|------|-------|
| JIT Code (PSRAM) | `SPIRAM \| 8BIT` | Large code, normal performance |
| JIT Code (Internal) | `INTERNAL \| 8BIT` | Small code, max performance |
| Args Buffer | `SPIRAM \| 8BIT` | Data only, any region OK |
| DMA Buffers | `DMA \| 8BIT` | Hardware constraints |

### 5.3 Shadow Allocation Table

**Purpose**: Track all device allocations on host side

**Data Structure**:
```python
self.allocations: Dict[int, dict] = {
    0x40800000: {
        'size': 2048,
        'caps': MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT,
        'align': 16
    },
    0x48200000: {
        'size': 128,
        'caps': MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT,
        'align': 16
    }
}
```

**Validation**:
```python
def write_memory(self, address, data):
    end_addr = address + len(data)
    valid = False
    
    for start, info in self.allocations.items():
        alloc_end = start + info['size']
        if start <= address and end_addr <= alloc_end:
            valid = True
            break
    
    if not valid:
        raise PermissionError(f"Segmentation Fault: 0x{address:08X}")
    
    # Safe to write
    self._send_packet(CMD_WRITE_MEM, ...)
```

**Benefits**:
- Prevents writing to unallocated memory
- Catches pointer errors before device crash
- No device-side overhead

### 5.4 Memory Allocation Lifecycle

![Memory Allocation Lifecycle](assets/memory-allocation-lifecycle.png)

**Image Prompt for `assets/memory-allocation-lifecycle.png`**:
```
Create a timeline diagram showing memory allocation lifecycle during JIT function loading.

HORIZONTAL TIMELINE (left to right):

TIME EVENTS:
1. "Pass 1: Probe Build"
   - Show: "No allocation"
   - Annotation: "Measure size only"

2. "Allocate Code Region"
   - Show: Rectangle in PSRAM area
   - Label: "0x40800000, 2112 bytes"
   - Color: Green (allocated)

3. "Allocate Args Region"
   - Show: Rectangle in PSRAM area
   - Label: "0x48200000, 128 bytes"
   - Color: Blue (allocated)

4. "Pass 2: Recompile"
   - Show: Same rectangles
   - Annotation: "Addresses locked in"

5. "Upload Code"
   - Show: Code rectangle filled with pattern
   - Annotation: "CMD_WRITE_MEM"

6. "Execute Function"
   - Show: Highlight code rectangle
   - Annotation: "Running"

7. "Smart Args: Allocate Arrays" (if applicable)
   - Show: Small temporary rectangles
   - Label: "Array data"
   - Color: Yellow (temporary)

8. "Free Arrays"
   - Show: Yellow rectangles disappear
   - Annotation: "CMD_FREE (automatic)"

9. "Function Complete"
   - Show: Green and Blue rectangles remain
   - Annotation: "Code still loaded"

10. "func.free() Called"
    - Show: All rectangles disappear
    - Annotation: "All memory released"

VERTICAL AXIS:
Show memory regions: PSRAM, with address markers

ANNOTATIONS:
- "Persistent Allocation" for code/args
- "Temporary Allocation" for arrays
- "Automatic Cleanup" for array deallocation

Use timeline style with boxes appearing/disappearing to show allocation/free.
Reference: p4jit.py:load() and smart_args.py:pack()/cleanup()
```

---

## 6. Type System

### 6.1 Supported Types

#### 6.1.1 Scalar Types

**Integers**:
```c
int8_t    // -128 to 127
uint8_t   // 0 to 255
int16_t   // -32768 to 32767
uint16_t  // 0 to 65535
int32_t   // -2147483648 to 2147483647
uint32_t  // 0 to 4294967295
```

**Floating Point**:
```c
float     // IEEE 754 single precision (32-bit)
```

**Pointers**:
```c
int*      // Any pointer type
float*
void*
struct_name*
```

#### 6.1.2 Unsupported Types

**64-bit Types**:
```c
int64_t   // NOT SUPPORTED
uint64_t  // NOT SUPPORTED
double    // TRUNCATED TO float
```

**Why**: Args buffer uses 4-byte slots, cannot fit 64-bit types

**Workaround**:
```c
// Instead of
void func(int64_t value);

// Use
void func(int32_t low, int32_t high);

// Host side
low = value & 0xFFFFFFFF
high = (value >> 32) & 0xFFFFFFFF
```

**Aggregate Returns**:
```c
struct Vec3 get_position();  // NOT SUPPORTED
Vec3[] get_array();          // NOT SUPPORTED
```

**Why**: RISC-V ABI returns large types via hidden pointer

**Workaround**:
```c
// Use output parameter
void get_position(Vec3 *out);
```

### 6.2 Type Mapping (C ↔ NumPy)

From `config/numpy_types.yaml`:

```yaml
type_map:
  "int8": "int8_t"
  "uint8": "uint8_t"
  "int16": "int16_t"
  "uint16": "uint16_t"
  "int32": "int32_t"
  "uint32": "uint32_t"
  "float32": "float"
  "float64": "double"  # WARNING: Truncated
```

**Smart Args Usage**:
```python
# Correct
func(np.int32(10), np.float32(3.14))

# Wrong
func(10, 3.14)  # Python int/float not allowed
```

---

## 7. Smart Args System

### 7.1 Complete Feature Set

**Automatic Operations**:
1. Type validation
2. Memory allocation for arrays
3. Binary packing
4. Execution
5. Return value conversion
6. Bidirectional array sync
7. Memory cleanup

### 7.2 Configuration

**Per-Function**:
```python
func = jit.load(source='code.c', function_name='process', smart_args=True)
```

**Sync Control**:
```python
# Enable sync (default)
func.sync_arrays = True

# Disable sync
func.sync_arrays = False
```

### 7.3 Return Value Handling

**Conversion Table**:

| C Return Type | Raw Bytes | Python Result |
|---------------|-----------|---------------|
| `void` | N/A | `None` |
| `int32_t` | `0xFFFFFFD6` | `np.int32(-42)` |
| `uint32_t` | `0xFFFFFFD6` | `np.uint32(4294967254)` |
| `float` | `0x40490FDB` | `np.float32(3.14159)` |
| `int*` | `0x40800000` | `np.uint32(0x40800000)` |

---

## 8. Communication Protocol

### 8.1 Packet Structure

```
+-------+-------+-------+-------+-------+-------+-------+-------+
|  0xA5 |  0x5A | CmdID | Flags |    Payload Length (LE)       |
+-------+-------+-------+-------+-------+-------+-------+-------+
|                                                               |
|                    Payload (Variable)                         |
|                                                               |
+-------+-------+-------+-------+-------+-------+-------+-------+
|          Checksum (LE)        |
+-------+-------+-------+-------+

Fields:
- Magic: 0xA5 0x5A (2 bytes)
- Command ID: 1 byte
- Flags: 1 byte (0x00=Request, 0x01=Response OK, 0x02=Error)
- Length: 4 bytes (uint32_t, little-endian)
- Payload: Variable
- Checksum: 2 bytes (uint16_t, sum of all previous bytes)
```

### 8.2 Command Reference

#### CMD_ALLOC (0x10)

**Request**:
```c
struct {
    uint32_t size;       // Bytes to allocate
    uint32_t caps;       // Memory capabilities
    uint32_t alignment;  // Alignment requirement
} __packed;
```

**Response**:
```c
struct {
    uint32_t address;    // Allocated address (0 if failed)
    uint32_t error;      // 0 = success
} __packed;
```

**Example**:
```
Request:  A5 5A 10 00 0C 00 00 00  00 08 00 00 00 04 00 00  10 00 00 00 XX XX
          ^     ^  ^  ^-Length--^  ^-Size 2048^ ^-Caps---^  ^-Align16^ ^Checksum
          Magic Cmd Flags

Response: A5 5A 10 01 08 00 00 00  00 00 80 40 00 00 00 00  XX XX
          ^     ^  ^  ^-Length--^  ^-Addr----^ ^-Error---^  ^Checksum
```

#### CMD_WRITE_MEM (0x20)

**Request**:
```c
struct {
    uint32_t address;    // Target address
    uint8_t data[];      // Data to write
} __packed;
```

**Response**:
```c
struct {
    uint32_t written;    // Bytes written
    uint32_t status;     // 0 = OK
} __packed;
```

#### CMD_EXEC (0x30)

**Request**:
```c
struct {
    uint32_t address;    // Function address
} __packed;
```

**Response**:
```c
struct {
    uint32_t retval;     // Function return value
} __packed;
```

---

## 9. Configuration

### 9.1 `config/toolchain.yaml`

**Complete Example**:
```yaml
toolchain:
  path: "C:/Espressif/tools/riscv32-esp-elf/esp-14.2.0/riscv32-esp-elf/bin"
  prefix: "riscv32-esp-elf"
  compilers:
    gcc: "riscv32-esp-elf-gcc"
    g++: "riscv32-esp-elf-g++"
    as: "riscv32-esp-elf-as"

extensions:
  compile:
    ".c": "gcc"
    ".cpp": "g++"
    ".cc": "g++"
    ".cxx": "g++"
    ".S": "gcc"
  headers:
    - ".h"
    - ".hpp"

compiler:
  arch: "rv32imafc_zicsr_zifencei_xesppie"
  abi: "ilp32f"
  optimization: "O3"
  flags:
    - "-ffreestanding"
    - "-fno-builtin"
    - "-ffunction-sections"
    - "-fdata-sections"
    - "-msmall-data-limit=0"
    - "-flto"

linker:
  garbage_collection: true
  flags:
    - "-flto"
  firmware_elf: "firmware/build/p4_jit_firmware.elf"

memory:
  max_size: "128K"
  alignment: 4

wrapper:
  template_file: "temp.c"
  wrapper_entry: "call_remote"
  args_array_size: 32
```

---

## 10. Limitations & Constraints

### 10.1 64-bit Type Limitation

**Problem**: Cannot pass or return 64-bit types

**Affected Types**: `int64_t`, `uint64_t`, `double`

**Root Cause**: 4-byte slot size in args buffer

**Impact**:
```c
// This will FAIL
double compute(int64_t a, double b) {
    return (double)a + b;
}
```

**Workaround**:
```c
// Split into 32-bit parts
float compute_split(int32_t a_low, int32_t a_high, 
                   float b_low, float b_high) {
    int64_t a = ((int64_t)a_high << 32) | a_low;
    double b = /* reconstruct from float parts */;
    return (float)result;  // Truncate
}
```

### 10.2 Thread Safety

**Constraint**: Wrapper system is NOT thread-safe

**Reason**: Shared args buffer at fixed address

**Safe Usage**:
```python
# Sequential calls (OK)
result1 = func(10, 20)
result2 = func(30, 40)
```

**Unsafe Usage**:
```python
# Concurrent calls (RACE CONDITION)
thread1 = Thread(target=lambda: func(10, 20))
thread2 = Thread(target=lambda: func(30, 40))
thread1.start()
thread2.start()
# Thread 2 may overwrite Thread 1's arguments!
```

**Solution**: External synchronization
```python
lock = threading.Lock()

with lock:
    result = func(10, 20)
```

---

## 11. Advanced Topics

### 11.1 L2MEM Execution

**Enable Internal SRAM Execution**:

In `firmware/sdkconfig.defaults.esp32p4`:
```kconfig
CONFIG_ESP_SYSTEM_PMP_IDRAM_SPLIT=n
```

**Allocate in L2MEM**:
```python
from p4jit.runtime.memory_caps import MALLOC_CAP_INTERNAL, MALLOC_CAP_8BIT

func = jit.load(
    source='tight_loop.c',
    function_name='dsp_filter',
    code_caps=MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT  # Internal SRAM
)
```

**When to Use**:
- Code < 768 KB
- Latency-critical loops
- Cache-miss sensitive algorithms

### 11.2 Cache Coherency

**Problem**: Separate I-Cache and D-Cache

**Solution**: `esp_cache_msync()` (automatic in firmware)

**What It Does**:
1. Flush D-Cache to RAM
2. Invalidate I-Cache
3. CPU fetches fresh instructions

**Alignment Requirement**: 128-byte cache line

---

## 12. API Reference

### 12.1 P4JIT Class

```python
class P4JIT:
    def __init__(self, port=None, config_path='config/toolchain.yaml')
    def load(self, source, function_name, **options) -> JITFunction
    def get_heap_stats(self, print_s=True) -> Dict[str, int]
```

### 12.2 JITFunction Class

```python
class JITFunction:
    def __call__(self, *args) -> Any
    def free(self) -> None
    
    @property
    def sync_arrays(self) -> bool
    
    @sync_arrays.setter
    def sync_arrays(self, value: bool)
    
    # Attributes
    binary: BinaryObject
    code_addr: int
    args_addr: int
```

### 12.3 BinaryObject Class

```python
class BinaryObject:
    # Properties
    data: bytes
    total_size: int
    base_address: int
    entry_address: int
    sections: Dict
    functions: List
    
    # Methods
    def save_bin(self, path)
    def save_elf(self, path)
    def save_metadata(self, path)
    def disassemble(self, output=None)
    def print_sections(self)
    def print_symbols(self)
    def print_memory_map(self)
```

---

## 13. Troubleshooting

### 13.1 Build Errors

**Error: "Function 'X' not found"**

Cause: Entry point name mismatch

Solution:
1. Check function name spelling
2. Verify function is on its own line
3. Check builder logs for available functions

---

**Error: "Firmware ELF not found"**

Cause: Invalid path in config

Solution:
```bash
cd firmware
idf.py build
# Update config/toolchain.yaml with correct path
```

---

### 13.2 Runtime Errors

**Error: "PermissionError: Segmentation Fault"**

Cause: Writing to unallocated memory

Solution: Check allocation logic, verify addresses

---

**Error: "Guru Meditation: IllegalInstruction"**

Causes:
1. Wrong ISA flags
2. Cache not synced
3. Code not uploaded

Solutions:
1. Verify `arch` in config matches ESP32-P4
2. Check firmware calls `esp_cache_msync()`
3. Verify upload success

---

## 14. Quick-Start Examples

### 14.1 Hello World

```python
import numpy as np
from p4jit import P4JIT

# Create source file
with open('add.c', 'w') as f:
    f.write("""
    int add(int a, int b) {
        return a + b;
    }
    """)

jit = P4JIT()
func = jit.load(source='add.c', function_name='add')

result = func(np.int32(10), np.int32(20))
print(f"Result: {result}")  # 30

func.free()
```

### 14.2 Array Processing

```python
import numpy as np
from p4jit import P4JIT

with open('scale.c', 'w') as f:
    f.write("""
    void scale_array(float* data, int len, float factor) {
        for(int i = 0; i < len; i++) {
            data[i] *= factor;
        }
    }
    """)

jit = P4JIT()
func = jit.load(source='scale.c', function_name='scale_array')

data = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
func(data, np.int32(len(data)), np.float32(2.5))

print(data)  # [2.5, 5.0, 7.5, 10.0]
```

### 14.3 Firmware Symbols

```python
from p4jit import P4JIT

with open('print_test.c', 'w') as f:
    f.write("""
    #include 
    
    int test_print(void) {
        printf("Hello from JIT!\\n");
        return 42;
    }
    """)

jit = P4JIT()
func = jit.load(
    source='print_test.c',
    function_name='test_print',
    use_firmware_elf=True
)

result = func()
# Device monitor shows: "Hello from JIT!"
print(f"Return: {result}")  # 42
```

---

## 15. Appendices

### Appendix A: Memory Capabilities

```python
MALLOC_CAP_EXEC             = (1<<0)
MALLOC_CAP_32BIT            = (1<<1)
MALLOC_CAP_8BIT             = (1<<2)
MALLOC_CAP_DMA              = (1<<3)
MALLOC_CAP_SPIRAM           = (1<<10)
MALLOC_CAP_INTERNAL         = (1<<11)
MALLOC_CAP_DEFAULT          = (1<<12)
MALLOC_CAP_IRAM_8BIT        = (1<<13)
MALLOC_CAP_RETENTION        = (1<<14)
MALLOC_CAP_RTCRAM           = (1<<15)
MALLOC_CAP_TCM              = (1<<16)
```

### Appendix B: Error Codes

```c
#define ERR_OK          0x00
#define ERR_CHECKSUM    0x01
#define ERR_UNKNOWN_CMD 0x02
#define ERR_ALLOC_FAIL  0x03
```

### Appendix C: RISC-V Register Reference

| Register | ABI Name | Purpose | Saved By |
|----------|----------|---------|----------|
| x0 | zero | Always 0 | N/A |
| x1 | ra | Return address | Caller |
| x2 | sp | Stack pointer | Callee |
| x8 | s0/fp | Frame pointer | Callee |
| x10-x11 | a0-a1 | Args/return | Caller |
| x12-x17 | a2-a7 | Arguments | Caller |
| f10-f11 | fa0-fa1 | Float args/return | Caller |
| f12-f17 | fa2-fa7 | Float args | Caller |

---

## 16. Image Generation Summary

All images to generate:

1. `assets/system-architecture.png` - System overview
2. `assets/builder-pipeline.png` - Build process
3. `assets/wrapper-memory-layout.png` - Args buffer structure
4. `assets/protocol-state-machine.png` - Protocol FSM
5. `assets/usb-data-flow.png` - USB communication
6. `assets/smart-args-flow.png` - Smart Args sequence
7. `assets/two-pass-linking.png` - Two-pass build
8. `assets/esp32p4-memory-map.png` - Memory regions
9. `assets/memory-allocation-lifecycle.png` - Allocation timeline
10. `assets/args-buffer-detailed.png` - Detailed buffer layout

---

**Document Version**: 2.0.0  
**Last Updated**: January 2025  
**Status**: Complete

---

**END OF TECHNICAL REFERENCE MANUAL**