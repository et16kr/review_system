__global__ void demo() { if (threadIdx.x) { __syncthreads(); } }
