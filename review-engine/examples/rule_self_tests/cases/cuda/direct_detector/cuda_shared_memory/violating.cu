extern __shared__ int tile[];
__global__ void demo() { tile[threadIdx.x] = 0; }
