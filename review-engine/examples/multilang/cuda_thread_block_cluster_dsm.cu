#include <cooperative_groups.h>

namespace cg = cooperative_groups;

__global__ void cluster_histogram(int* bins, const int* input, int count) {
    extern __shared__ int smem[];
    auto cluster = cg::this_cluster();
    int bucket = threadIdx.x % 32;

    smem[bucket] = 0;
    if (cluster.block_rank() == 0) {
        cluster.sync();
    }

    int* remote_hist = cluster.map_shared_rank(
        smem,
        (cluster.block_rank() + 1) % cluster.num_blocks());
    atomicAdd(remote_hist + bucket, input[bucket % count]);
    cluster.sync();

    if (cluster.block_rank() == 0 && threadIdx.x == 0) {
        bins[bucket] = smem[bucket];
    }
}

void launch_cluster_histogram(int* bins, const int* input, int count) {
    dim3 blocks(6, 1, 1);
    dim3 threads(128, 1, 1);
    cluster_histogram<<<blocks, threads, 128 * sizeof(int)>>>(bins, input, count);
}
