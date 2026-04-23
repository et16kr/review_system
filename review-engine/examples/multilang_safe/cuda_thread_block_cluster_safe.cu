#include <cooperative_groups.h>

namespace cg = cooperative_groups;

__global__ __cluster_dims__(2, 1, 1)
void cluster_histogram_safe(int* bins, const int* input, int count) {
    extern __shared__ int smem[];
    auto cluster = cg::this_cluster();
    int bucket = threadIdx.x % 32;

    smem[bucket] = 0;
    cluster.sync();

    int dst_block_rank = (cluster.block_rank() + 1) % cluster.num_blocks();
    int* remote_hist = cluster.map_shared_rank(smem, dst_block_rank);
    atomicAdd(remote_hist + bucket, input[bucket % count]);
    cluster.sync();

    if (cluster.block_rank() == 0 && threadIdx.x == 0) {
        bins[0] = smem[0];
    }
}

void launch_cluster_histogram_safe(int* bins, const int* input, int count) {
    dim3 blocks(6, 1, 1);
    dim3 threads(128, 1, 1);
    cluster_histogram_safe<<<blocks, threads, 128 * sizeof(int)>>>(bins, input, count);
}
