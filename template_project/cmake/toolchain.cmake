SET(CMAKE_SYSTEM_NAME Generic)

# RV32GC processor
SET(CMAKE_SYSTEM_PROCESSOR Pulp)

SET(CMAKE_C_COMPILER ${TC_PREFIX}gcc${EXE_EXT})
SET(CMAKE_CXX_COMPILER ${TC_PREFIX}g++${EXE_EXT})
SET(CMAKE_ASM_COMPILER ${TC_PREFIX}gcc${EXE_EXT})
SET(CMAKE_LINKER ${TC_PREFIX}ld${EXE_EXT})
SET(CMAKE_OBJCOPY ${TC_PREFIX}objcopy${EXE_EXT})
SET(CMAKE_AR ${TC_PREFIX}ar${EXE_EXT})
SET(CMAKE_RANLIB ${TC_PREFIX}ranlib${EXE_EXT})

# The linker argument setting below will break the cmake test program on 64-bit, so disable test program linking for
# now.
SET(CMAKE_TRY_COMPILE_TARGET_TYPE "STATIC_LIBRARY")

SET(CMAKE_CXX_FLAGS  "${CMAKE_CXX_FLAGS} -msmall-data-limit=8 -mno-save-restore -fsigned-char -g3 -D__PULP_USE_LIBC -DSTDIO_FAKE=2 -DSTDIO_UART=1 -DSTDIO_NULL=0 -DCONFIG_STDIO=2 -DportasmHANDLE_INTERRUPT=undefined_handler")
SET(CMAKE_C_FLAGS  "${CMAKE_C_FLAGS} -msmall-data-limit=8 -mno-save-restore -fsigned-char -std=gnu11 -Wall -Wextra -Wshadow -Wformat=2 -Wundef -Wsign-conversion -Wno-unused-parameter -g3 -D__PULP_USE_LIBC -DSTDIO_FAKE=2 -DSTDIO_UART=1 -DSTDIO_NULL=0 -DCONFIG_STDIO=2")
SET(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -msmall-data-limit=8 -mno-save-restore -fsigned-char -std=gnu11 -Wall -Wextra -Wshadow -Wformat=2 -Wundef -Wsign-conversion -Wno-unused-parameter -g3 -nostartfiles -Wl,--gc-sections -Wl,-Map,memory.map")