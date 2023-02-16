# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import atexit
import collections
import collections.abc
import enum
import fcntl
import logging
import os
import os.path
import pathlib
import queue
import re
import select
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import json
import signal

import yaml

from tvm.micro.project_api import server


_LOG = logging.getLogger(__name__)


API_SERVER_DIR = pathlib.Path(os.path.dirname(__file__) or os.path.getcwd())


BUILD_DIR = API_SERVER_DIR / "build"


MODEL_LIBRARY_FORMAT_RELPATH = "model.tar"

MEMORY_SIZE_BYTES = 2 * 1024 * 1024

IS_TEMPLATE = not (API_SERVER_DIR / MODEL_LIBRARY_FORMAT_RELPATH).exists()

def check_call(cmd_args, *args, **kwargs):
    cwd_str = "" if "cwd" not in kwargs else f" (in cwd: {kwargs['cwd']})"
    _LOG.debug("run%s: %s", cwd_str, " ".join(shlex.quote(a) for a in cmd_args))
    return subprocess.check_call(cmd_args, *args, **kwargs)


CACHE_ENTRY_RE = re.compile(r"(?P<name>[^:]+):(?P<type>[^=]+)=(?P<value>.*)")


CMAKE_BOOL_MAP = dict(
    [(k, True) for k in ("1", "ON", "YES", "TRUE", "Y")]
    + [(k, False) for k in ("0", "OFF", "NO", "FALSE", "N", "IGNORE", "NOTFOUND", "")]
)


class CMakeCache(collections.abc.Mapping):
    def __init__(self, path):
        self._path = path
        self._dict = None

    def __iter__(self):
        return iter(self._dict)

    def __getitem__(self, key):
        if self._dict is None:
            self._dict = self._read_cmake_cache()

        return self._dict[key]

    def __len__(self):
        return len(self._dict)

    def _read_cmake_cache(self):
        """Read a CMakeCache.txt-like file and return a dictionary of values."""
        entries = collections.OrderedDict()
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                m = CACHE_ENTRY_RE.match(line.rstrip("\n"))
                if not m:
                    continue

                if m.group("type") == "BOOL":
                    value = CMAKE_BOOL_MAP[m.group("value").upper()]
                else:
                    value = m.group("value")

                entries[m.group("name")] = value

        return entries


CMAKE_CACHE = CMakeCache(BUILD_DIR / "CMakeCache.txt")


class BoardError(Exception):
    """Raised when an attached board cannot be opened (i.e. missing /dev nodes, etc)."""


PROJECT_TYPES = []
if IS_TEMPLATE:
    for d in (API_SERVER_DIR / "src").iterdir():
        if d.is_dir():
            PROJECT_TYPES.append(d.name)


PROJECT_OPTIONS = [
    server.ProjectOption(
        "toolchain",
        optional=["build", "flash", "open_transport"],
        type="str",
        choices=["llvm", "gcc"], # I do not know how to parse it. 
        help="Choose the toolchain from llvm and gcc.",
    ),
    server.ProjectOption(
        "pulp_freertos_path",
        optional=["build", "flash", "open_transport"],
        type="str",
        help="Path to the installed pulp-freertos directory.",
    ),
    server.ProjectOption(
        "pulp_gcc_path",
        optional=["build"],
        type="str",
        help="Path to the installed Pulp GCC directory.",
    ),
    server.ProjectOption(
        "pulp_llvm_path",
        optional=["build"],
        type="str",
        help="Path to the installed Pulp LLVM directory.",
    ),
    server.ProjectOption(
        "trace_file",
        optional=["flash"],
        type="bool",
        default=False,
        help="Write instruction trace to file.",
    ),
    server.ProjectOption(
        "memory_size_bytes",
        optional=["generate_project"],
        type="int",
        default=MEMORY_SIZE_BYTES,
        help="Sets the value of MEMORY_SIZE_BYTES.",
    ),
    server.ProjectOption(
        "project_type",
        choices=tuple(PROJECT_TYPES),
        required=["generate_project"],
        type="str",
        help="Type of project to generate.",
    ),
    server.ProjectOption("verbose", optional=["build"], type="bool", help="Run build with verbose output."),
    server.ProjectOption("debug", optional=["build"], type="bool", help="Run build in DEBUG mode."),
]


class Handler(server.ProjectAPIHandler):
    def __init__(self):
        super(Handler, self).__init__()
        self._proc = None

    def server_info_query(self, tvm_version):
        return server.ServerInfo(
            platform_name="gvsoc",
            is_template=IS_TEMPLATE,
            model_library_format_path=""
            if IS_TEMPLATE
            else (API_SERVER_DIR / MODEL_LIBRARY_FORMAT_RELPATH),
            project_options=PROJECT_OPTIONS,
        )

    # These files and directories will be recursively copied into generated projects from the CRT.
    CRT_COPY_ITEMS = ("include", "Makefile", "src")

    API_SERVER_CRT_LIBS_TOKEN = "<API_SERVER_CRT_LIBS>"

    # Common needs to be first in the list as other libs depend on it
    CRT_LIBS_BY_PROJECT_TYPE = {
        "host_driven": "common microtvm_rpc_server microtvm_rpc_common graph_executor graph_executor_module aot_executor aot_executor_module",
    }

    def generate_project(self, model_library_format_path, standalone_crt_dir, project_dir, options):

        project_dir = pathlib.Path(project_dir)
        # Make project directory.
        project_dir.mkdir()

        # Copy ourselves to the generated project. TVM may perform further build steps on the generated project
        # by launching the copy.
        shutil.copy2(__file__, project_dir / os.path.basename(__file__))

        # Place Model Library Format tarball in the special location, which this script uses to decide
        # whether it's being invoked in a template or generated project.
        project_model_library_format_tar_path = project_dir / MODEL_LIBRARY_FORMAT_RELPATH
        shutil.copy2(model_library_format_path, project_model_library_format_tar_path)

        # Extract Model Library Format tarball.into <project_dir>/model.
        extract_path = os.path.splitext(project_model_library_format_tar_path)[0]
        with tarfile.TarFile(project_model_library_format_tar_path) as tf:
            os.makedirs(extract_path)
            tf.extractall(path=extract_path)

        # Populate CRT.
        crt_path = project_dir / "crt"
        crt_path.mkdir()
        for item in self.CRT_COPY_ITEMS:
            src_path = os.path.join(standalone_crt_dir, item)
            dst_path = crt_path / item
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dst_path)
            else:
                shutil.copy2(src_path, dst_path)

        # Populate Makefile.
        with open(API_SERVER_DIR / "CMakeLists.txt.template", "r") as cmake_template_f:
            with open(project_dir / "CMakeLists.txt", "w") as cmake_f:
                for line in cmake_template_f:
                    if self.API_SERVER_CRT_LIBS_TOKEN in line:
                        crt_libs = self.CRT_LIBS_BY_PROJECT_TYPE[options["project_type"]]
                        line = line.replace("<API_SERVER_CRT_LIBS>", crt_libs)

                    cmake_f.write(line)

        #self._create_prj_conf(project_dir, options)

        # Populate crt-config.h
        crt_config_dir = project_dir / "crt_config"
        crt_config_dir.mkdir()
        shutil.copy2(
            API_SERVER_DIR / "crt_config" / "crt_config.h", crt_config_dir / "crt_config.h"
        )

        # Populate src/
        src_dir = project_dir / "src"
        shutil.copytree(API_SERVER_DIR / "src" / options["project_type"], src_dir)

        # Populate cmake/
        cmake_dir = project_dir / "cmake"
        shutil.copytree(API_SERVER_DIR / "cmake", cmake_dir)

    def build(self, options):
        BUILD_DIR.mkdir()

        cmake_args = ["cmake", ".."]
        assert options.get("toolchain") in ["llvm", "gcc"], f"toolchain must be llvm or gcc but get {options.get('toolchain')}"
        cmake_args.append("-DTOOLCHAIN=" + options["toolchain"])

        if options.get("pulp_freertos_path"):
            cmake_args.append("-DPULP_FREERTOS_DIR=" + options["pulp_freertos_path"])
        else:
            raise RuntimeError("Project Config 'pulp_freertos_path' undefined!")

        if options.get("pulp_gcc_path"):
            cmake_args.append("-DRISCV_ELF_GCC_PREFIX=" + options["pulp_gcc_path"])
        else:
            raise RuntimeError("Project Config 'pulp_gcc_path' undefined!")

        if options.get("pulp_llvm_path"):
            cmake_args.append("-DLLVM_DIR=" + options["pulp_llvm_path"])
        else:
            raise RuntimeError("Project Config 'pulp_llvm_path' undefined!")

        if options.get("memory_size_bytes"):
            b = int(options["memory_size_bytes"])
            if b > 0:
                cmake_args.append("-DMEMORY_SIZE_BYTES=" + str(b))

        if options.get("debug"):
            cmake_args.append("-DCMAKE_BUILD_TYPE=DEBUG")

        if options.get("verbose"):
            cmake_args.append("-DCMAKE_VERBOSE_MAKEFILE:BOOL=TRUE")

        if options.get("verbose"):
            check_call(cmake_args, cwd=BUILD_DIR)
        else:
            check_call(cmake_args, cwd=BUILD_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        # print("BUILD_DIR", BUILD_DIR)
        # input(">")
        args = ["make", "-j2"]
        if options.get("verbose"):
            args.append("VERBOSE=1")
            check_call(args, cwd=BUILD_DIR)
        else:
            check_call(args, cwd=BUILD_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    def flash(self, options):
        pass  # Flashing does nothing on host.

    def _set_nonblock(self, fd):
        flag = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flag | os.O_NONBLOCK)
        new_flag = fcntl.fcntl(fd, fcntl.F_GETFL)
        assert (new_flag & os.O_NONBLOCK) != 0, "Cannot set file descriptor {fd} to non-blocking"

    def open_transport(self, options):
        # print("open_transport")
        env = os.environ
        env["PULP_RISCV_GCC_TOOLCHAIN"] = options["pulp_gcc_path"]
        gvsoc_args = []
        gvsoc_args.append(options["pulp_freertos_path"] + "/support/egvsoc.sh")
        gvsoc_args.append(f"--dir={BUILD_DIR}")
        gvsoc_args.append("--config-file=pulp@config_file=chips/pulp/pulp.json")
        gvsoc_args.append("--platform=gvsoc")
        gvsoc_args.append("--binary=app")
        gvsoc_args.append("prepare")
        gvsoc_args.append("run")
        # print("env", env)
        # print("cwd", BUILD_DIR)
        # print("gvsoc_args", gvsoc_args)
        self._proc = subprocess.Popen(
            gvsoc_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0, cwd=BUILD_DIR, env=env
        )
        self._set_nonblock(self._proc.stdin.fileno())
        self._set_nonblock(self._proc.stdout.fileno())
        return server.TransportTimeouts(
            session_start_retry_timeout_sec=0,
            session_start_timeout_sec=0,
            session_established_timeout_sec=0,
        )

    def close_transport(self):
        # print("close_transport")
        if self._proc is not None:
            proc = self._proc
            self._proc = None
            proc.terminate()
            proc.wait()

    def _await_ready(self, rlist, wlist, timeout_sec=None, end_time=None):
        if timeout_sec is None and end_time is not None:
            timeout_sec = max(0, end_time - time.monotonic())

        rlist, wlist, xlist = select.select(rlist, wlist, rlist + wlist, timeout_sec)
        if not rlist and not wlist and not xlist:
            raise server.IoTimeoutError()

        return True

    def read_transport(self, n, timeout_sec):
        # print("read_transport", n, timeout_sec)
        if self._proc is None:
            raise server.TransportClosedError()

        fd = self._proc.stdout.fileno()
        # print("fd", fd)
        end_time = None if timeout_sec is None else time.monotonic() + timeout_sec

        try:
            self._await_ready([fd], [], end_time=end_time)
            # print("os.ready")
            to_return = os.read(fd, n)
            # print("->", to_return)
        except BrokenPipeError:
            to_return = 0

        if not to_return:
            self.disconnect_transport()
            raise server.TransportClosedError()

        return to_return

    def write_transport(self, data, timeout_sec):
        # print("write_transport", data, timeout_sec)
        if self._proc is None:
            raise server.TransportClosedError()

        fd = self._proc.stdin.fileno()
        # print("fd", fd)
        end_time = None if timeout_sec is None else time.monotonic() + timeout_sec

        data_len = len(data)
        while data:
            self._await_ready([], [fd], end_time=end_time)
            try:
                # print("os.write")
                num_written = os.write(fd, data)
            except BrokenPipeError:
                num_written = 0

            if not num_written:
                self.disconnect_transport()
                raise server.TransportClosedError()

            data = data[num_written:]


if __name__ == "__main__":
    server.main(Handler())
