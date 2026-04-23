#include <cuda_runtime.h>

void overlap_copy_safe(float* host_dst, const float* device_src, size_t bytes) {
    cudaStream_t stream;
    cudaEvent_t ready;
    cudaStreamCreateWithFlags(&stream, cudaStreamNonBlocking);
    cudaEventCreate(&ready);
    cudaMemcpyAsync(host_dst, device_src, bytes, cudaMemcpyDeviceToHost, stream);
    cudaEventRecord(ready, stream);
    cudaStreamWaitEvent(stream, ready, 0);
    cudaEventDestroy(ready);
    cudaStreamDestroy(stream);
}
