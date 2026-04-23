#include <cuda_runtime.h>

__global__ void accumulate(float* dst, const float* src, int n) {
    extern __shared__ float scratch[];
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (threadIdx.x == 0) {
        __syncthreads();
    }
    if (idx < n) {
        scratch[threadIdx.x] = src[idx];
        atomicAdd(&dst[0], scratch[threadIdx.x]);
    }
}

void run_kernel(float* host_out, const float* host_in, int n) {
    float* device_out = nullptr;
    cudaMalloc(&device_out, sizeof(float));
    accumulate<<<(n + 255) / 256, 256, 256 * sizeof(float)>>>(device_out, host_in, n);
    cudaMemcpy(host_out, device_out, sizeof(float), cudaMemcpyDeviceToHost);
    cudaDeviceSynchronize();
}
