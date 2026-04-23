#include <cuda_runtime.h>

void copy_to_host(float* host_dst, const float* device_src, size_t bytes, cudaStream_t stream) {
    cudaMemcpyAsync(host_dst, device_src, bytes, cudaMemcpyDeviceToHost, stream);
    cudaStreamSynchronize(stream);
}
