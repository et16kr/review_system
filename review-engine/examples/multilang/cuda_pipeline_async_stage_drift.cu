#include <cuda/barrier>
#include <cuda/pipeline>
#include <cooperative_groups.h>

namespace cg = cooperative_groups;

__device__ void consume_stage(float* out, const float* tile, int count) {
    if (threadIdx.x < count) {
        out[threadIdx.x] += tile[threadIdx.x];
    }
}

__global__ void stage_tiles(float* out, const float* in, int tiles) {
    extern __shared__ float smem[];
    __shared__ cuda::pipeline_shared_state<cuda::thread_scope_block, 2> pipe_state;
    __shared__ cuda::barrier<cuda::thread_scope_block> ready;
    auto block = cg::this_thread_block();
    auto pipe = cuda::make_pipeline(block, &pipe_state);

    if (block.thread_rank() == 0) {
        init(&ready, block.size());
    }
    block.sync();

    for (int tile = 0; tile < tiles; ++tile) {
        int stage = tile % 2;
        float* shared_tile = smem + stage * block.size();

        if (threadIdx.x == 0) {
            pipe.producer_acquire();
        }
        cuda::memcpy_async(
            block,
            shared_tile,
            in + tile * block.size(),
            cuda::aligned_size_t<4>(sizeof(float) * block.size()),
            pipe);
        consume_stage(out, shared_tile, block.size());
        if (threadIdx.x == 0) {
            pipe.producer_commit();
            pipe.consumer_wait();
        }
        if (threadIdx.x < 16) {
            ready.arrive_and_wait();
        }
        pipe.consumer_release();
    }
}
