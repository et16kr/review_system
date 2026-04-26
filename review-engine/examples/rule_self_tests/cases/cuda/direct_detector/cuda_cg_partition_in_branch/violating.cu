void demo() { if (threadIdx.x) { tiled_partition<32>(block); } }
