# P4-JIT Component

A high-performance dynamic code loading system for ESP32-P4 microcontrollers, enabling execution of native RISC-V machine code compiled on-the-fly from a host PC.

## Overview

The P4-JIT component provides a USB-based protocol for dynamic code loading and execution on the ESP32-P4. Unlike interpreted languages or bytecode VMs, this system executes **native, optimized RISC-V machine code**, delivering maximum performance for computationally intensive tasks.

### Key Features

- **Native Code Execution**: Direct RISC-V instruction execution with zero interpreter overhead
- **USB High-Speed Transport**: Efficient binary protocol over TinyUSB CDC-ACM
- **Dynamic Memory Management**: Runtime allocation with capability control (PSRAM/SRAM, executable/data)
- **Cache Coherency**: Automatic instruction/data cache synchronization
- **FreeRTOS Integration**: Non-blocking operation via dedicated task and stream buffers
- **Configurable**: Full control over task priority, core affinity, and buffer sizes

### Use Cases

- Digital Signal Processing (DSP) algorithms
- Real-time control loops
- Cryptographic operations
- Machine learning inference kernels
- Rapid prototyping without firmware reflashing

## Architecture

```
Host PC                          ESP32-P4
┌────────────────┐              ┌─────────────────┐
│  Python Client │              │  USB Transport  │
│  (p4_jit)      │◄────USB─────►│  (TinyUSB CDC)  │
└────────────────┘              └────────┬────────┘
                                         │
                                ┌────────▼────────┐
                                │ Protocol Parser │
                                │  (State Machine)│
                                └────────┬────────┘
                                         │
                                ┌────────▼────────┐
                                │ Command Handler │
                                │  (Dispatcher)   │
                                └────────┬────────┘
                                         │
                      ┌──────────────────┼──────────────────┐
                      │                  │                  │
               ┌──────▼──────┐  ┌────────▼────────┐  ┌─────▼─────┐
               │   Memory    │  │  Code Executor  │  │   Cache   │
               │  Manager    │  │  (Function Call)│  │  Manager  │
               └─────────────┘  └─────────────────┘  └───────────┘
```

## Dependencies

### Required IDF Components
- `esp_timer` - High-resolution timing
- `driver` - Hardware abstraction
- `esp_rom` - ROM functions
- `esp_mm` - Memory management
- `heap` - Heap allocator
- `log` - Logging system

### External Dependencies
- `espressif/esp_tinyusb` (v2.0.1+) - USB stack

### System Requirements
- ESP-IDF v5.0 or later
- ESP32-P4 target hardware
- PSRAM enabled (recommended 16MB+)

## Installation

### 1. Add Component to Your Project

Copy the `p4_jit` component to your project:
```bash
cp -r /path/to/p4_jit components/
```

### 2. Configure System Requirements

Append the following to your project's `sdkconfig.defaults.esp32p4`:

```kconfig
# Memory Protection - CRITICAL FOR JIT EXECUTION
CONFIG_ESP_SYSTEM_PMP_IDRAM_SPLIT=n
CONFIG_SOC_SPIRAM_XIP_SUPPORTED=y

# External PSRAM
CONFIG_SPIRAM=y
CONFIG_SPIRAM_SPEED_200M=y

# Cache Configuration
CONFIG_CACHE_L2_CACHE_256KB=y
CONFIG_CACHE_L2_CACHE_LINE_128B=y

# Watchdogs (Disable for debugging)
CONFIG_ESP_INT_WDT=n
CONFIG_ESP_TASK_WDT_EN=n

# USB Communication
CONFIG_TINYUSB_CDC_ENABLED=y
CONFIG_TINYUSB_CDC_COUNT=1
CONFIG_TINYUSB_CDC_RX_BUFSIZE=2048
CONFIG_TINYUSB_CDC_TX_BUFSIZE=2048

# Experimental Features
CONFIG_IDF_EXPERIMENTAL_FEATURES=y
```

### 3. Update Dependencies

```bash
idf.py add-dependency "espressif/esp_tinyusb^2.0.1"
idf.py reconfigure
```

## Configuration Options

Configure via `idf.py menuconfig` → `P4-JIT Configuration`:

| Option | Default | Description |
|:-------|:--------|:------------|
| `P4_JIT_TASK_STACK_SIZE` | 8192 | Stack size for protocol task (bytes) |
| `P4_JIT_TASK_PRIORITY` | 5 | FreeRTOS task priority (0-25) |
| `P4_JIT_TASK_CORE_ID` | 1 | CPU core assignment (-1=no affinity, 0/1=specific core) |
| `P4_JIT_PAYLOAD_BUFFER_SIZE` | 1048576 | RX/TX buffer for code transfer (1MB default) |
| `P4_JIT_STREAM_BUFFER_SIZE` | 16384 | USB ISR ring buffer (16KB default) |

### Recommended Settings

**Development:**
- Task Priority: 5
- Core ID: 1 (leave Core 0 for Wi-Fi/system)
- Payload Buffer: 1MB (PSRAM)

**Production:**
- Task Priority: 10+ (if JIT is critical path)
- Core ID: 1 (dedicated core for deterministic latency)
- Stream Buffer: 32KB (reduce packet loss under load)

## API Reference

### Initialization

```c
#include "p4_jit.h"

void app_main(void) {
    // Start with default configuration
    ESP_ERROR_CHECK(p4_jit_start(NULL));
    
    // Your application continues running...
}
```

### Custom Configuration

```c
p4_jit_config_t config = {
    .task_priority = 10,
    .task_core_id = 1,
    .stack_size = 16384,
    .rx_buffer_size = 0,  // Reserved for future use
    .tx_buffer_size = 0   // Reserved for future use
};

ESP_ERROR_CHECK(p4_jit_start(&config));
```

### Shutdown (Experimental)

```c
// Currently not fully implemented
ESP_ERROR_CHECK(p4_jit_stop());
```

## Communication Protocol

### Packet Format

```
Offset | Field     | Size | Description
-------|-----------|------|----------------------------------
0      | Magic     | 2    | 0xA5 0x5A (sync bytes)
2      | Command   | 1    | Command ID (see table below)
3      | Flags     | 1    | 0x00=Request, 0x01=OK, 0x02=Error
4      | Length    | 4    | Payload length (little-endian)
8      | Payload   | N    | Command-specific data
8+N    | Checksum  | 2    | Sum(Header + Payload) & 0xFFFF
```

### Supported Commands

| Command ID | Name | Description |
|:-----------|:-----|:------------|
| 0x01 | PING | Echo test (payload loopback) |
| 0x10 | ALLOC | Allocate memory with capabilities |
| 0x11 | FREE | Release allocated memory |
| 0x20 | WRITE_MEM | Write binary data to address |
| 0x21 | READ_MEM | Read binary data from address |
| 0x30 | EXEC | Execute code at address |

### Memory Capabilities

Use ESP-IDF heap capabilities flags:

```c
// Common combinations
MALLOC_CAP_SPIRAM                  // External PSRAM
MALLOC_CAP_INTERNAL                // Internal SRAM
MALLOC_CAP_8BIT                    // Byte-accessible
MALLOC_CAP_EXEC | MALLOC_CAP_8BIT  // Executable code region
```

## Integration Example

### Minimal Application

```c
#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "p4_jit.h"

static const char *TAG = "main";

void app_main(void)
{
    ESP_LOGI(TAG, "Starting Application with P4-JIT");

    // Initialize JIT engine (runs in background)
    ESP_ERROR_CHECK(p4_jit_start(NULL));

    ESP_LOGI(TAG, "JIT Engine ready. Connect via USB.");

    // Main application loop
    while (1) {
        // Your application logic here
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
```

### Build and Flash

```bash
idf.py set-target esp32p4
idf.py build
idf.py flash monitor
```

## Troubleshooting

### Issue: `Guru Meditation Error: IllegalInstruction`

**Cause:** Memory protection (PMP) blocking code execution from data regions.

**Solution:** Ensure `CONFIG_ESP_SYSTEM_PMP_IDRAM_SPLIT=n` is set.

### Issue: USB Device Not Enumerated

**Cause:** TinyUSB not configured or conflicting USB console.

**Solution:** 
- Verify `CONFIG_TINYUSB_CDC_ENABLED=y`
- Disable USB console: `CONFIG_ESP_CONSOLE_USB_CDC=n`

### Issue: Cache Sync Errors

**Cause:** Misaligned addresses for `esp_cache_msync()`.

**Solution:** The component automatically aligns to 128-byte cache lines. If errors persist, increase allocation alignment on the host side.

### Issue: Task Watchdog Triggered

**Cause:** JIT task blocked during long operations.

**Solution:** Disable watchdogs during development:
```kconfig
CONFIG_ESP_TASK_WDT_EN=n
```

### Issue: Memory Allocation Failures

**Cause:** Insufficient PSRAM or fragmentation.

**Solution:** 
- Check available heap: `heap_caps_get_free_size(MALLOC_CAP_SPIRAM)`
- Enable PSRAM: `CONFIG_SPIRAM=y`
- Increase `P4_JIT_PAYLOAD_BUFFER_SIZE` if needed

## Performance Characteristics

### Throughput
- **USB Transfer Rate**: ~10-12 MB/s (High-Speed mode)
- **Code Upload Time**: ~100ms for 1MB binary
- **Execution Latency**: <10µs (function call overhead)

### Memory Requirements
- **Component RAM**: ~8KB (task stack + buffers)
- **Component PSRAM**: Configurable (default 1MB for payload buffers)
- **Per-Function Overhead**: 0 bytes (direct function pointer calls)

## License

MIT License - See project root for full license text.

## Support

For issues related to this component:
1. Check the main project README at `/README.md`
2. Verify sdkconfig settings match requirements
3. Enable verbose logging: `idf.py menuconfig` → Component config → Log output → Verbose

## Version History

- **v1.0.0** - Initial release
  - USB High-Speed transport
  - Dynamic memory allocation
  - Cache coherency management
  - FreeRTOS task integration
