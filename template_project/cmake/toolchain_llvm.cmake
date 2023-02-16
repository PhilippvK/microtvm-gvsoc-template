# Contains toolchain configurations and settings for using LLVM/Clang

INCLUDE(LookupClang)

MESSAGE(STATUS "CLANG_EXECUTABLE=${CLANG_EXECUTABLE}")
MESSAGE(STATUS "CLANG++_EXECUTABLE=${CLANG++_EXECUTABLE}")
MESSAGE(STATUS "LLD_EXECUTABLE=${LLD_EXECUTABLE}")

SET(CMAKE_C_COMPILER ${CLANG_EXECUTABLE})
SET(CMAKE_CXX_COMPILER ${CLANG++_EXECUTABLE})
SET(CMAKE_ASM_COMPILER ${CLANG_EXECUTABLE})
# set(CMAKE_C_LINKER lld-13) # TODO(fabianpedd): doesnt work, need to use -fuse-ld=lld-13 instead


# RV32GC processor
SET(CMAKE_SYSTEM_PROCESSOR Pulpissimo)

# The linker argument setting below will break the cmake test program on 64-bit, so disable test program linking for
# now.
SET(CMAKE_TRY_COMPILE_TARGET_TYPE "STATIC_LIBRARY")

# the following is transfered from PULP-FreeRTOS repository
# https://github.com/pulp-platform/pulp-freertos/blob/master/default_flags.mk#L110-L126
# Builtin mandatory flags. Need to be simply expanded variables for appends in
# other cmake files to work correctly
SET(CV_CFLAGS "\
--target=riscv32 \
--gcc-toolchain=${RISCV_ELF_GCC_PREFIX} --sysroot=${RISCV_ELF_GCC_PREFIX}/${RISCV_ELF_GCC_BASENAME} \
-msmall-data-limit=8 -mno-save-restore \
-fsigned-char -ffunction-sections -fdata-sections \
-Wall -Wextra -Wshadow -Wformat=2 -Wundef -Wsign-conversion -Wno-unused-parameter") # -std=gnu11 \

SET(CV_ASFLAGS "\
--target=riscv32 \
--gcc-toolchain=${RISCV_ELF_GCC_PREFIX} --sysroot=${RISCV_ELF_GCC_PREFIX}/${RISCV_ELF_GCC_BASENAME} \
-msmall-data-limit=8 -mno-save-restore \
-fsigned-char -ffunction-sections -fdata-sections \
-x assembler-with-cpp")

SET(CV_CPPFLAGS "--target=riscv32 --gcc-toolchain=${RISCV_ELF_GCC_PREFIX} --sysroot=${RISCV_ELF_GCC_PREFIX}/${RISCV_ELF_GCC_BASENAME}")

# note: linkerscript is included in target directory makefile.mk
SET(CV_LDFLAGS "\
-nostartfiles \
-Wl,--gc-sections \
-Wl,-Map,memory.map") # -Wl,--print-gc-sections

# LIST(APPEND CV_LDFLAGS " -Wstack-usage=1024")

# the following is transfered from PULP-FreeRTOS repository
# https://github.com/pulp-platform/pulp-freertos/blob/master/default_targets.mk#L77-L87
SET(CMAKE_CXX_FLAGS  "${CMAKE_CXX_FLAGS} ${CV_CFLAGS} ${CV_CPPFLAGS} -DSTDIO_FAKE=2 -DSTDIO_UART=1 -DSTDIO_NULL=0 -DCONFIG_STDIO=2 ")
SET(CMAKE_C_FLAGS  "${CMAKE_C_FLAGS} ${CV_CFLAGS} ${CV_CPPFLAGS} -DSTDIO_FAKE=2 -DSTDIO_UART=1 -DSTDIO_NULL=0 -DCONFIG_STDIO=2 ")
SET(CMAKE_ASM_FLAGS "${CMAKE_ASM_FLAGS} ${CV_ASFLAGS} ${CV_CPPFLAGS} -DportasmHANDLE_INTERRUPT=vSystemIrqHandler ")
SET(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -DportasmHANDLE_INTERRUPT=vSystemIrqHandler ${CV_CFLAGS} -g3 ${CV_LDFLAGS}")