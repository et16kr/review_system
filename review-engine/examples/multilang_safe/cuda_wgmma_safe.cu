#include <cuda/ptx>

__device__ void epilogue_store_safe(half* out, const float* accum) {
    out[threadIdx.x] = __float2half_rn(accum[threadIdx.x % 64]);
}

__global__ void warpgroup_gemm_safe(const uint64_t* desc_a, const uint64_t* desc_b, half* out) {
    __shared__ float accum[64];

    asm volatile("wgmma.fence.sync.aligned;");
    asm volatile("wgmma.mma_async.sync.aligned.m64n128k16.f32.f16.f16");
    asm volatile("wgmma.commit_group.sync.aligned;");
    asm volatile("wgmma.wait_group.sync.aligned 0;");

    epilogue_store_safe(out, accum);
}
