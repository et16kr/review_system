void demo(void* d, void* h) { cudaMemcpyAsync(d, h, 64, cudaMemcpyHostToDevice, 0); }
