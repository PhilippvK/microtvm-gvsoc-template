# microtvm-gvsoc-template

This repository contains a MicroTVM ProjectAPI Template for the GVSoC (Pulp) target alongside set of example scripts to get started.

## Prerequisites

### Install required packages

TODO (cmake, ...)

### Install GCC toolchain

Any multilib RISC-V compiler should work for the default set of extensions. Example Download: TODO

If you are going to use XPULP instructions, build your own `pulp_gcc` (see TODO) or download a prebuilt one here: TODO

### Install LLVM toolchain (optional)

Install a modern LLVM version (e.g. 14.0) if you only plan to use standard extensions: TODO

For supporting XPULP instructions, feel free to build your own `pulp_llvm` (see TODO) or download a prebuilt one here: TODO

### Install PULP FreeRTOS

TODO

### Install TVM

TODO

### Install PULP-FreeRTOS

## Usage

### Using TVMC Command Line

TODO

### Using Python Scripts

Please refer to one of the following example scripts:

- `micro_autotune_gvsoc.py`: Example how to tune a single `conv2d` layer using AutoTVM on GVSoC target
- `micro_autotune_gvsoc_rpc.py`: Example how to tune a single `conv2d` layer using AutoTVM on GVSoC target (via RPC Server) [WIP]
- `micro_autotune_gvsoc_tflite.py`: Example how to tune a complete TFLite model using AutoTVM on GVSoC
- `micro_tflite_gvsoc.py`: Example how to run a complete TFLite Model using AutoTVM on GVSoC

Make sure to to export the following environment variables beforehand:

```
export PYTHONPATH=/path/to/tvm/python  # only required using custom tvm build
export PULP_FREERTOS_DIR=/path/to/pulp_freertos
export PULP_GCC_DIR=/path/to/pulp_gcc
export PULP_LLVM_DIR=/path/to/pulp_llvm  # leave empty if unused


```

**Debugging Tipps:** TODO

## Configuration Options

- `verbose`: `true`/`false`
- `debug`: `true`/`false`
- `toolchain`: `gcc`/`llvm`
- `arch`: i.e. `rv32imc`
- `abi`: i.e. `ilp32`
- `pulp_freertos_path`: TODO
- `pulp_gcc_path`: TODO
- `pulp_llvm_path`: TODO
- `trace_file`: TODO
- `memory_size_bytes`: TODO
- `project_type`: i.e. `host_driven`

## Open TODOs

- [ ] Support Pulpissimo
- [ ] Increase memory size in linker file
- [ ] Support CV32E40P core (Core-V MCU)
