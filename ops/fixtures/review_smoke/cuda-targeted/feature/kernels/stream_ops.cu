#include <cuda_runtime.h>

void CUDART_CB on_done(void* user_data) {
    (void)user_data;
}

void copy_to_host(float* host_dst, const float* device_src, size_t bytes, int iters) {
    for (int i = 0; i < iters; ++i) {
        cudaStream_t stream;
        cudaStreamCreate(&stream);
        cudaMemcpyAsync(host_dst, device_src, bytes, cudaMemcpyDeviceToHost, 0);
        cudaLaunchHostFunc(stream, on_done, host_dst);
        cudaStreamDestroy(stream);
    }
}
