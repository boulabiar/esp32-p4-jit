# P4-JIT Protocol Specification

## Protocol Version: 1.0

This document describes the binary protocol used for communication between the host (Python) and the ESP32-P4 device over USB CDC.

## Packet Format

All packets follow this structure:

```
┌─────────┬──────────┬───────┬─────────┬──────────┬──────────┐
│ Magic   │ CmdID    │ Flags │ Length  │ Payload  │ Checksum │
│ 2 bytes │ 1 byte   │ 1 byte│ 4 bytes │ N bytes  │ 2 bytes  │
└─────────┴──────────┴───────┴─────────┴──────────┴──────────┘
```

- **Magic**: `0xA5 0x5A` (identifies start of packet)
- **CmdID**: Command identifier
- **Flags**: `0x00` for request, `0x01` for success response, `0x02` for error response
- **Length**: Payload length in bytes (little-endian uint32)
- **Payload**: Command-specific data
- **Checksum**: Sum of all preceding bytes, truncated to 16 bits (little-endian)

## Commands

### CMD_PING (0x01)

Echo test for connectivity verification.

**Request Payload**: Any bytes (typically `0xCA 0xFE 0xBA 0xBE`)
**Response Payload**: Same bytes echoed back

### CMD_GET_INFO (0x02)

Query device capabilities and protocol version. **Added in v1.0.**

**Request Payload**: Empty

**Response Payload** (32 bytes):
```
Offset  Size  Field
0       1     protocol_version_major
1       1     protocol_version_minor
2       2     reserved
4       4     max_payload_size (effective maximum, considers all buffers)
8       4     cache_line_size
12      4     max_allocations
16      16    firmware_version (null-terminated string)
```

### CMD_ALLOC (0x10)

Allocate memory on device.

**Request Payload** (12 bytes):
```
Offset  Size  Field
0       4     size (bytes to allocate)
4       4     caps (ESP-IDF MALLOC_CAP_* flags)
8       4     alignment (must be non-zero power of 2)
```

**Response Payload** (8 bytes):
```
Offset  Size  Field
0       4     address (0 on failure)
4       4     error_code (0 on success)
```

### CMD_FREE (0x11)

Free previously allocated memory.

**Request Payload** (4 bytes):
```
Offset  Size  Field
0       4     address
```

**Response Payload** (4 bytes):
```
Offset  Size  Field
0       4     status (0 on success)
```

### CMD_WRITE_MEM (0x20)

Write data to device memory.

**Request Payload** (8 + N bytes): **Changed in v1.0**
```
Offset  Size  Field
0       4     address
4       1     flags (bit 0: skip_bounds)
5       3     reserved
8       N     data
```

**Response Payload** (8 bytes):
```
Offset  Size  Field
0       4     bytes_written
4       4     status (0 on success)
```

### CMD_READ_MEM (0x21)

Read data from device memory.

**Request Payload** (12 bytes): **Changed in v1.0**
```
Offset  Size  Field
0       4     address
4       4     size
8       1     flags (bit 0: skip_bounds)
9       3     reserved
```

**Response Payload**: Raw bytes read from memory

### CMD_EXEC (0x30)

Execute code at specified address.

**Request Payload** (4 bytes):
```
Offset  Size  Field
0       4     address
```

**Response Payload** (4 bytes):
```
Offset  Size  Field
0       4     return_value
```

### CMD_HEAP_INFO (0x40)

Query heap memory statistics.

**Request Payload**: Empty

**Response Payload** (16 bytes):
```
Offset  Size  Field
0       4     free_spiram
4       4     total_spiram
8       4     free_internal
12      4     total_internal
```

## Request Flags

Used in CMD_WRITE_MEM and CMD_READ_MEM:

| Bit | Name | Description |
|-----|------|-------------|
| 0 | SKIP_BOUNDS | Bypass allocation table validation (for external buffers) |
| 1-7 | Reserved | Must be 0 |

## Error Codes

| Code | Name | Description |
|------|------|-------------|
| 0x00 | ERR_OK | Success |
| 0x01 | ERR_CHECKSUM | Checksum mismatch |
| 0x02 | ERR_UNKNOWN_CMD | Unknown command ID |
| 0x03 | ERR_ALLOC_FAIL | Memory allocation failed |
| 0x04 | ERR_INVALID_ADDR | Address not in allocation table |

## Version History

### v1.0 (Current)

Initial versioned release. Breaking changes from unversioned protocol:

- **CMD_GET_INFO added**: Query protocol version and device capabilities
- **CMD_WRITE_MEM header changed**: 4 bytes → 8 bytes (added flags + reserved)
- **CMD_READ_MEM header changed**: 8 bytes → 12 bytes (added flags + reserved)
- **Device-side allocation tracking**: All memory operations validated against allocation table
- **skip_bounds flag**: Allows bypassing validation for external memory access

### Pre-v1.0 (Legacy)

Original unversioned protocol. Not compatible with v1.0 host/device.

- CMD_WRITE_MEM: 4-byte header (address only)
- CMD_READ_MEM: 8-byte header (address + size only)
- No allocation tracking on device
- No CMD_GET_INFO

## Compatibility

Protocol version checking is performed on connection:

1. Host sends CMD_GET_INFO
2. Device responds with version info
3. Host validates `protocol_version_major` matches expected version
4. Connection proceeds or fails with version mismatch error

**Major version mismatch**: Incompatible, connection refused
**Minor version mismatch**: Warning only, may have reduced functionality
