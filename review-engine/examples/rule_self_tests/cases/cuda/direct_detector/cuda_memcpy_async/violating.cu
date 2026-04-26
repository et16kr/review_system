void demo(void* d, void* h, cudaStream_t s) { cudaMemcpyAsync(d, h, 64, cudaMemcpyHostToDevice, s); }
