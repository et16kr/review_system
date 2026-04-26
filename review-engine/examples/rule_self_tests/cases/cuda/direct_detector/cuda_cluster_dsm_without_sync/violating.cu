void demo() { if (threadIdx.x) { cluster.sync(); } map_shared_rank(ptr, 1); atomicAdd(ptr, 1); }
