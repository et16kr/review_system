#include <cuda_runtime.h>
#include <nccl.h>

void run_collective(
    float* device0,
    float* device1,
    size_t elements,
    cudaStream_t* streams,
    ncclComm_t* comms,
    int gpu_count
) {
    for (int device = 0; device < gpu_count; ++device) {
        cudaSetDevice(device);
    }

    cudaDeviceEnablePeerAccess(1, 0);
    cudaMemcpyPeerAsync(device1, 1, device0, 0, elements * sizeof(float), streams[0]);

    ncclGroupStart();
    ncclAllReduce((const void*)device0, device0, elements, ncclFloat, ncclSum, comms[0], streams[0]);
    ncclAllReduce((const void*)device1, device1, elements, ncclFloat, ncclSum, comms[1], streams[1]);
    ncclGroupEnd();
}
