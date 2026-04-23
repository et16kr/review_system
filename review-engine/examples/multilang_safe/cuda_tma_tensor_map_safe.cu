#include <cuda.h>
#include <cuda/barrier>
#include <cuda/ptx>
#include <utility>

namespace ptx = cuda::ptx;

using block_barrier = cuda::barrier<cuda::thread_scope_block>;

__device__ void consume_tile_safe(const int4 tile[8][8], float* out) {
    out[threadIdx.x % 8] += static_cast<float>(tile[threadIdx.x % 8][0].x);
}

__global__ void load_tile_tma_safe(
    const __grid_constant__ CUtensorMap tensor_map,
    const __grid_constant__ CUtensorMap template_tensor_map,
    float* out,
    CUtensorMap* published_map) {
    __shared__ alignas(128) CUtensorMap smem_tmap;
    __shared__ alignas(1024) int4 smem_tile[8][8];
    __shared__ block_barrier bar;

    block_barrier::arrival_token token;

    if (threadIdx.x == 0) {
        init(&bar, blockDim.x);
        smem_tmap = template_tensor_map;
        ptx::tensormap_replace_global_address(ptx::space_shared, &smem_tmap, out);

        ptx::n32_t<128> bytes_128;
        ptx::tensormap_cp_fenceproxy(
            ptx::sem_release,
            ptx::scope_gpu,
            published_map,
            &smem_tmap,
            bytes_128);

        int32_t coords[2] = {0, 0};
        ptx::cp_async_bulk_tensor(
            ptx::space_shared,
            ptx::space_global,
            &smem_tile,
            &tensor_map,
            coords,
            cuda::device::barrier_native_handle(bar));
        token = cuda::device::barrier_arrive_tx(bar, 1, sizeof(smem_tile));
    } else {
        token = bar.arrive();
    }

    bar.wait(std::move(token));
    consume_tile_safe(smem_tile, out);
}
