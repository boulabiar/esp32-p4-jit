# Memory Capabilities
MALLOC_CAP_EXEC             = (1<<0)  # Memory must be able to run executable code
MALLOC_CAP_32BIT            = (1<<1)  # Memory must allow for aligned 32-bit data accesses
MALLOC_CAP_8BIT             = (1<<2)  # Memory must allow for 8/16/...-bit data accesses
MALLOC_CAP_DMA              = (1<<3)  # Memory must be able to accessed by DMA
MALLOC_CAP_PID2             = (1<<4)  # Memory must be mapped to PID2 memory space
MALLOC_CAP_PID3             = (1<<5)  # Memory must be mapped to PID3 memory space
MALLOC_CAP_PID4             = (1<<6)  # Memory must be mapped to PID4 memory space
MALLOC_CAP_PID5             = (1<<7)  # Memory must be mapped to PID5 memory space
MALLOC_CAP_PID6             = (1<<8)  # Memory must be mapped to PID6 memory space
MALLOC_CAP_PID7             = (1<<9)  # Memory must be mapped to PID7 memory space
MALLOC_CAP_SPIRAM           = (1<<10) # Memory must be in SPI RAM
MALLOC_CAP_INTERNAL         = (1<<11) # Memory must be internal
MALLOC_CAP_DEFAULT          = (1<<12) # Memory can be returned in a non-capability-specific memory allocation
MALLOC_CAP_IRAM_8BIT        = (1<<13) # Memory must be in IRAM and allow unaligned access
MALLOC_CAP_RETENTION        = (1<<14) # Memory must be able to accessed by retention DMA
MALLOC_CAP_RTCRAM           = (1<<15) # Memory must be in RTC fast memory
MALLOC_CAP_TCM              = (1<<16) # Memory must be in TCM memory
MALLOC_CAP_DMA_DESC_AHB     = (1<<17) # Memory must be capable of containing AHB DMA descriptors
MALLOC_CAP_DMA_DESC_AXI     = (1<<18) # Memory must be capable of containing AXI DMA descriptors
MALLOC_CAP_CACHE_ALIGNED    = (1<<19) # Memory must be aligned to the cache line size
MALLOC_CAP_SIMD             = (1<<20) # Memory must be capable of being used for SIMD instructions

MALLOC_CAP_INVALID          = (1<<31) # Memory can't be used / list end marker
