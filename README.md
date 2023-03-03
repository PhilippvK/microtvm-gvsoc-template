# microtvm-gvsoc-template

This repository contains a MicroTVM ProjectAPI Template for the GVSoC (Pulp) target alongside set of example scripts to get started.

## Prerequisites

### Setup Python dependencies

Create and enter an virtual environment first:

```
virtualenv -p python3.8 venv
source venv/bin/activate
```

Install recommended packages for  running the examples:

```
pip install -r requirements.txt
```

### Install required packages

On Ubuntu 20.04 the following packages are required:

```bash
sudo apt install -y python3 python3-dev python3-setuptools gcc libtinfo-dev zlib1g-dev build-essential cmake libedit-dev libxml2-dev git
```

### Install GCC toolchain

Any multilib RISC-V compiler should work for the default set of extensions. Example Download: https://github.com/stnolting/riscv-gcc-prebuilt

If you are going to use XPULP instructions, build your own `pulp_gcc` (see https://github.com/pulp-platform/pulp-riscv-gnu-toolchain) or download a prebuilt one here: https://github.com/pulp-platform/pulp-riscv-gnu-toolchain/releases/download/v1.0.16/v1.0.16-pulp-riscv-gcc-ubuntu-18.tar.bz2

### Install LLVM toolchain (optional)

Install a modern LLVM version (e.g. 14.0) if you only plan to use standard extensions: https://releases.llvm.org/download.html

For supporting XPULP instructions, feel free to build your own `pulp_llvm` (see https://github.com/pulp-platform/llvm-project) or download a prebuilt one here: https://versaweb.dl.sourceforge.net/project/pulp-llvm-project/nightly/riscv32-pulp-llvm-ubuntu2004.tar.gz

### Install PULP FreeRTOS + GVSoC

Follow instructions here: https://github.com/pulp-platform/pulp-freertos

TLDR;

```
git clone https://github.com/pulp-platform/pulp-freertos.git
export RISCV=/path/to/riscv/gcc
git submodule update --init --recursive
cd pulp-freertos
source env/pulp.sh
cp -r template/hello_world helloworld
cd helloworld
pip install pyelftools prettytable six
make all
make run-gvsoc  # implicitly installs gvsoc simulator
```

### Install TVM

Follow instructions here: https://tvm.apache.org/docs/install/from_source.html

**Warning:** The options `USE_MICRO`, `USE_MICRO_STANDALONE_RUNTIME` and `USE_LLVM` have to be enabled in `config.cmake` before compilation.


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


## Configuration Options

- `verbose`: `true`/`false` (Wether compiler messages should be printed out during compilation. Useful for debugging errors)
- `debug`: `true`/`false` (Build executable in DEBUG instead of RELEASE mode)
- `toolchain`: `gcc`/`llvm` (Choose prefered SW toolchain/compiler)
- `arch`: i.e. `rv32imc` (RISC-V arch to use during compilation)
- `abi`: i.e. `ilp32` (RISC-V abi to use during compilation)
- `trace_file`: `true`/`false` (Write trace of executed instruction to a file)
- `memory_size_bytes`: e.g. `131072` (Size of the used memory arena for runtime allocations. Limited by sections in liker script. Minimum depends on workload.)
- `project_type`: i.e. `host_driven`
- `pulp_freertos_path`/`pulp_gcc_path`/`pulp_llvm_path` (Path to dependencies)


## Open TODOs

- [ ] Support Pulpissimo
- [ ] Increase memory size in linker file
- [ ] Support CV32E40P core (Core-V MCU)
