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
"""
.. _microTVM-with-TFLite:

microTVM with TFLite Models
===========================
**Author**: `Tom Gall <https://github.com/tom-gall>`_

This tutorial is an introduction to working with microTVM and a TFLite
model with Relay.
"""

# Load and prepare the Pre-Trained Model
# --------------------------------------

import os
import numpy as np
import logging
import sys
from pathlib import Path

#logging.basicConfig(level="DEBUG", stream=sys.stdout)

import tvm
import tvm.micro as micro
from tvm.contrib.download import download_testdata
from tvm.contrib import graph_executor, utils
from tvm import relay

DIR = Path(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
ETISS_DIR = os.environ.get("ETISS_DIR", None)
assert ETISS_DIR, "Missing environment variable: ETISS_DIR"
RISCV_DIR = os.environ.get("RISCV_DIR", None)
assert RISCV_DIR, "Missing environment variable: RISCV_DIR"
# ETISSVP_SCRIPT = os.environ.get("ETISSVP_SCRIPT", str(DIR / "template_project" / "scripts" / "run.sh"))
ETISSVP_SCRIPT = os.environ.get("ETISSVP_SCRIPT", str(Path(ETISS_DIR) / "bin" / "run_helper.sh"))
assert ETISSVP_SCRIPT, "Missing environment variable: ETISSVP_SCRIPT"
ETISSVP_INI = os.environ.get("ETISSVP_INI", str(DIR / "template_project" / "scripts" / "memsegs.ini"))
assert ETISSVP_INI, "Missing environment variable: ETISSVP_INI"

project_options = {
    "project_type": "host_driven",
    "verbose": False,
    "debug": False,
    "transport": True,
    "etiss_path": ETISS_DIR,
    "riscv_path": RISCV_DIR,
    "etissvp_script": ETISSVP_SCRIPT,
    "etissvp_script_args": "plic clint uart v" + (" -i" + ETISSVP_INI if ETISSVP_INI else "")
}

model_url = "https://people.linaro.org/~tom.gall/sine_model.tflite"
model_file = "sine_model.tflite"
model_path = download_testdata(model_url, model_file, module="data")

tflite_model_buf = open(model_path, "rb").read()

######################################################################
# Using the buffer, transform into a tflite model python object
try:
    import tflite

    tflite_model = tflite.Model.GetRootAsModel(tflite_model_buf, 0)
except AttributeError:
    import tflite.Model

    tflite_model = tflite.Model.Model.GetRootAsModel(tflite_model_buf, 0)

######################################################################
# Print out the version of the model
version = tflite_model.Version()
print("Model Version: " + str(version))

######################################################################
# Parse the python model object to convert it into a relay module
# and weights.
# It is important to note that the input tensor name must match what
# is contained in the model.
#
# If you are unsure what that might be, this can be discovered by using
# the ``visualize.py`` script within the Tensorflow project.
# See `How do I inspect a .tflite file? <https://www.tensorflow.org/lite/guide/faq>`_

input_tensor = "dense_4_input"
input_shape = (1,)
input_dtype = "float32"

mod, params = relay.frontend.from_tflite(
    tflite_model, shape_dict={input_tensor: input_shape}, dtype_dict={input_tensor: input_dtype}
)

######################################################################
# Defining the target
# -------------------
#

# Compiling for virtual hardware
TARGET = tvm.target.target.micro("host")
RUNTIME = tvm.relay.backend.Runtime("crt", {"system-lib": True})
BOARD = "bare_etiss_processor"

######################################################################
# Now, compile the model for the target:

with tvm.transform.PassContext(
    opt_level=3, config={"tir.disable_vectorize": True}, disabled_pass=["AlterOpLayout"]
):
    module = relay.build(mod, target=TARGET, runtime=RUNTIME, params=params)
    print("module", module)


# Inspecting the compilation output
# ---------------------------------

c_source_module = module.get_lib().imported_modules[0]
assert c_source_module.type_key == "c", "tutorial is broken"

c_source_code = c_source_module.get_source()

# Compiling the generated code
# ----------------------------

# Get a temporary path where we can store the tarball (since this is running as a tutorial).
import tempfile

fd, model_library_format_tar_path = tempfile.mkstemp()
os.close(fd)
os.unlink(model_library_format_tar_path)
tvm.micro.export_model_library_format(module, model_library_format_tar_path)

import tarfile

with tarfile.open(model_library_format_tar_path, "r:*") as tar_f:
    print("\n".join(f" - {m.name}" for m in tar_f.getmembers()))

# Cleanup for tutorial:
os.unlink(model_library_format_tar_path)

import subprocess
import pathlib

# Compiling for virtual hardware
# ------------------------------

# Create a temporary directory
import tvm.contrib.utils

temp_dir = tvm.contrib.utils.tempdir()
generated_project_dir = temp_dir / "generated-project"
generated_project = tvm.micro.generate_project(
    str(DIR / "template_project"), module, generated_project_dir, project_options
)

# Build and flash the project
generated_project.build()
generated_project.flash()

with tvm.micro.Session(transport_context_manager=generated_project.transport()) as session:
    graph_mod = tvm.micro.create_local_graph_executor(
        module.get_graph_json(), session.get_system_lib(), session.device
    )

    graph_mod.set_input(**module.get_params())

    graph_mod.set_input(input_tensor, tvm.nd.array(np.array([0.5], dtype="float32")))
    graph_mod.run()

    tvm_output = graph_mod.get_output(0).numpy()
    print("result is: " + str(tvm_output))
