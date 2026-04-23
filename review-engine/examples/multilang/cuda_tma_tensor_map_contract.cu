#include <cuda.h>
#include <cuda/barrier>
#include <cuda/ptx>

namespace ptx = cuda::ptx;

__device__ void consume_tile(const int4 tile[8][8], float* out) {
    out[threadIdx.x % 8] += static_cast<float>(tile[threadIdx.x % 8][0].x);
}

__global__ void load_tile_tma(CUtensorMap* tensor_map, float* out) {
    __shared__ alignas(128) CUtensorMap smem_tmap;
    __shared__ alignas(1024) int4 smem_tile[8][8];
    __shared__ cuda::barrier<cuda::thread_scope_block> bar;

    if (threadIdx.x == 0) {
        init(&bar, blockDim.x);
        smem_tmap = *tensor_map;
        ptx::tensormap_replace_global_address(ptx::space_shared, &smem_tmap, out);

        int32_t coords[2] = {0, 0};
        ptx::cp_async_bulk_tensor(
            ptx::space_shared,
            ptx::space_global,
            &smem_tile,
            tensor_map,
            coords,
            cuda::device::barrier_native_handle(bar));
        cuda::device::barrier_arrive_tx(bar, 1, sizeof(smem_tile));
    }
    __syncthreads();

    consume_tile(smem_tile, out);

    if (threadIdx.x == 0) {
        int32_t next_coords[2] = {8, 0};
        ptx::cp_async_bulk_tensor(
            ptx::space_shared,
            ptx::space_global,
            &smem_tile,
            &smem_tmap,
            next_coords,
            cuda::device::barrier_native_handle(bar));
    }
}
