void demo() { if (threadIdx.x % 32) { wmma::mma_sync(acc, a, b, acc); } }
