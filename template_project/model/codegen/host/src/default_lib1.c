#include <inttypes.h>
#include <tvm/runtime/metadata_types.h>
#include <tvm/runtime/c_runtime_api.h>
static const struct TVMTensorInfo kTvmgenMetadata_inputs[0] = {
};
static const struct TVMTensorInfo kTvmgenMetadata_outputs[0] = {
};
static const struct TVMTensorInfo kTvmgenMetadata_workspace_pools[0] = {
};
static const struct TVMConstantInfo kTvmgenMetadata_constant_pools[0] = {
};
static const struct TVMMetadata kTvmgenMetadata[1] = {
{
1L /* version*/, 
kTvmgenMetadata_inputs, 
0L /* num_inputs*/, 
kTvmgenMetadata_outputs, 
0L /* num_outputs*/, 
kTvmgenMetadata_workspace_pools, 
0L /* num_workspace_pools*/, 
kTvmgenMetadata_constant_pools, 
0L /* num_constant_pools*/, 
"tvmgen_default" /* mod_name*/}
};
#ifdef __cplusplus
extern "C"
#endif
TVM_DLL int32_t tvmgen_default_get_c_metadata(TVMValue* arg_values, int* arg_tcodes, int num_args, TVMValue* ret_values, int* ret_tcodes, void* resource_handle) {
    ret_values[0].v_handle = (void*) &kTvmgenMetadata;
    ret_tcodes[0] = kTVMOpaqueHandle;
    return 0;
};
