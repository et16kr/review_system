__global__ void demo() { if (threadIdx.x % 32) { work(); } }
