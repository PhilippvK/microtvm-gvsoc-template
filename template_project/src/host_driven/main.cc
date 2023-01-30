/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

/*
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include <tvm/runtime/crt/logging.h>
#include <tvm/runtime/crt/microtvm_rpc_server.h>
#include <tvm/runtime/crt/graph_executor_module.h>
#include <unistd.h>

#include "crt_config.h"


#define CSR_PULP_PCMR 0xCC1
#define CSR_PULP_PCER 0xCC0
#define CSR_PULP_PCCR0 0x780

#define csr_write(csr, val)         \
({                \
  unsigned long __v = (unsigned long)(val);   \
  __asm__ ("csrw " #csr ", %0" \
            : : "rK" (__v)      \
            : "memory");      \
})

#define csr_read(csr)           \
({                \
  register unsigned long __v;       \
  __asm__ ("csrr %0, " #csr  \
            : "=r" (__v) :      \
            : "memory");      \
  __v;              \
  })


enum semihosting_operation_numbers {
	/*
	 * ARM/openocd semihosting operations.
	 * extracted from openocd semihosting_commong.h file
	 */
	SEMIHOSTING_ENTER_SVC = 0x17,	/* DEPRECATED */

	SEMIHOSTING_SYS_CLOCK = 0x10,
	SEMIHOSTING_SYS_ELAPSED = 0x30,

	SEMIHOSTING_SYS_ERRNO = 0x13,

	SEMIHOSTING_SYS_EXIT = 0x18,
	SEMIHOSTING_SYS_EXIT_EXTENDED = 0x20,
	// stat
	SEMIHOSTING_SYS_FLEN = 0x0C,
	SEMIHOSTING_SYS_GET_CMDLINE = 0x15,
	SEMIHOSTING_SYS_HEAPINFO = 0x16,
	SEMIHOSTING_SYS_ISERROR = 0x08,
	SEMIHOSTING_SYS_ISTTY = 0x09,

	// File operations
	SEMIHOSTING_SYS_OPEN = 0x01,
	SEMIHOSTING_SYS_CLOSE = 0x02,
	SEMIHOSTING_SYS_READ = 0x06,
	SEMIHOSTING_SYS_READC = 0x07,
	SEMIHOSTING_SYS_REMOVE = 0x0E,
	SEMIHOSTING_SYS_RENAME = 0x0F,
	SEMIHOSTING_SYS_SEEK = 0x0A,
	SEMIHOSTING_SYS_WRITE = 0x05,
	SEMIHOSTING_SYS_WRITEC = 0x03,
	// roughly a printf (print a string terminated by '\0')
	SEMIHOSTING_SYS_WRITE0 = 0x04,

	SEMIHOSTING_SYS_SYSTEM = 0x12,
	SEMIHOSTING_SYS_TICKFREQ = 0x31,
	SEMIHOSTING_SYS_TIME = 0x11,
	SEMIHOSTING_SYS_TMPNAM = 0x0D,
};

/* riscv semihosting standard:
 * IN: a0 holds syscall number
 * IN: a1 holds pointer to arg struct
 * OUT: a0 holds return value (if exists)
 */
static inline long
__internal_semihost(long n, long _a1)
{
  register long a0 __asm("a0") = n;
  register long a1 __asm("a1") = _a1;

  // riscv magic values for semihosting
  __asm volatile (
          ".option norvc;\t\n"
		  "slli    zero,zero,0x1f\t\n"
		  "ebreak\t\n"
		  "srai    zero,zero,0x7\t\n"
          ".option rvc;\t\n"
		: "+r"(a0)
		: "r"(a1)
		);
  return a0;
}

int semihost_read(int fd, uint8_t *buffer, int len)
{
    volatile uint32_t args[3] = {(uint32_t)fd,(uint32_t)buffer,(uint32_t)len};
    return __internal_semihost(SEMIHOSTING_SYS_READ, (long) args);
}

int semihost_write(int fd, uint8_t *buffer, int len)
{
    volatile uint32_t args[3] = {(uint32_t)fd,(uint32_t)buffer,(uint32_t)len};
    return __internal_semihost(SEMIHOSTING_SYS_WRITE, (long) args);
}


/* Loops/exits simulation */
void exit(int i);


static const struct device* tvm_uart;

static size_t g_num_bytes_requested = 0;
static size_t g_num_bytes_written = 0;


volatile uint32_t ticks = 0;

// Called by TVM to write serial data to the UART.
ssize_t write_serial(void* unused_context, const uint8_t* data, size_t size) {
  g_num_bytes_requested += size;

  semihost_write(STDOUT_FILENO, (uint8_t*)data, size);
  g_num_bytes_written += size;

  return size;
}

// Called by TVM when a message needs to be formatted.
size_t TVMPlatformFormatMessage(char* out_buf, size_t out_buf_size_bytes, const char* fmt,
                                va_list args) {
  return vsnprintf(out_buf, out_buf_size_bytes, fmt, args);
}

// Called by TVM when an internal invariant is violated, and execution cannot continue.
void TVMPlatformAbort(tvm_crt_error_t error) {
  TVMLogf("TVMError: 0x%x", error);
  // TODO
  exit(1);
}

// Called by TVM to generate random data.
tvm_crt_error_t TVMPlatformGenerateRandom(uint8_t* buffer, size_t num_bytes) {
  uint32_t random;  // one unit of random data.

  // Fill parts of `buffer` which are as large as `random`.
  size_t num_full_blocks = num_bytes / sizeof(random);
  for (int i = 0; i < num_full_blocks; ++i) {
    //random = sys_rand32_get();
    // TODO
    memcpy(&buffer[i * sizeof(random)], &random, sizeof(random));
  }

  // Fill any leftover tail which is smaller than `random`.
  size_t num_tail_bytes = num_bytes % sizeof(random);
  if (num_tail_bytes > 0) {
    memcpy(&buffer[num_bytes - num_tail_bytes], &random, num_tail_bytes);
  }
  return kTvmErrorNoError;
}

tvm_crt_error_t TVMPlatformMemoryAllocate(size_t num_bytes, DLDevice dev, void** out_ptr) {
  TVMLogf("TVMPlatformMemoryAllocate %u\n", num_bytes);
  if (num_bytes == 0) {
    num_bytes = sizeof(int);
  }
  *out_ptr = malloc(num_bytes);
  return (*out_ptr == NULL) ? kTvmErrorPlatformNoMemory : kTvmErrorNoError;
}

tvm_crt_error_t TVMPlatformMemoryFree(void* ptr, DLDevice dev) {
  TVMLogf("TVMPlatformMemoryFree\n");
  free(ptr);
  return kTvmErrorNoError;
}


unsigned int g_utvm_start_time_micros;
int g_utvm_timer_running = 0;

tvm_crt_error_t TVMPlatformTimerStart() {
  if (g_utvm_timer_running) {
    return kTvmErrorPlatformTimerBadState;
  }
  g_utvm_timer_running = 1;
  csr_write(0xCC0, 0b11);
  g_utvm_start_time_micros = csr_read(0x780);

  return kTvmErrorNoError;
}

tvm_crt_error_t TVMPlatformTimerStop(double* elapsed_time_seconds) {
  if (!g_utvm_timer_running) {
    return kTvmErrorPlatformTimerBadState;
  }
  g_utvm_timer_running = 0;
  int g_utvm_stop_time = csr_read(0x780);
  if (g_utvm_stop_time < g_utvm_start_time_micros) { // overflow
    *elapsed_time_seconds = (((uint64_t)1 << 32) - (g_utvm_start_time_micros - g_utvm_stop_time)) / 100000000.0;
  } else {
    *elapsed_time_seconds = (g_utvm_stop_time - g_utvm_start_time_micros) / 100000000.0;
  }
  return kTvmErrorNoError;
}


int main(void) {

  // Initialize microTVM RPC server, which will receive commands from the UART and execute them.
  microtvm_rpc_server_t server = MicroTVMRpcServerInit(write_serial, NULL);
  CHECK_EQ(TVMGraphExecutorModule_Register(), kTvmErrorNoError,
           "failed to register GraphExecutor TVMModule");
  TVMLogf("microTVM GVSoC runtime - running");

  // The main application loop. We continuously read commands from the UART
  // and dispatch them to MicroTVMRpcServerLoop().
  while (true) {

    uint8_t c;
    int ret_code = 1 - semihost_read(STDIN_FILENO, &c, 1);
    if (ret_code < 0) {
      // perror("microTVM runtime: read failed");
      return 1;
    } else if (ret_code == 0) {
      return 2;
    }
    uint8_t* cursor = &c;
    size_t bytes_remaining = 1;

    uint8_t* arr_ptr = &c;
    while (bytes_remaining > 0) {
      // Pass the received bytes to the RPC server.
      tvm_crt_error_t err = MicroTVMRpcServerLoop(server, &arr_ptr, &bytes_remaining);
      if (err != kTvmErrorNoError && err != kTvmErrorFramingShortPacket) {
        TVMPlatformAbort(err);
      }
      if (g_num_bytes_written != 0 || g_num_bytes_requested != 0) {
        if (g_num_bytes_written != g_num_bytes_requested) {
          TVMPlatformAbort((tvm_crt_error_t)0xbeef5);
        }
        g_num_bytes_written = 0;
        g_num_bytes_requested = 0;
      }
    }
  }

  TVMLogf("microTVM GVSoC  runtime - done");
  return 0;

}
