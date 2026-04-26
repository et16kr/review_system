void demo() { if (threadIdx.x == 0) { pipe.producer_acquire(); } }
