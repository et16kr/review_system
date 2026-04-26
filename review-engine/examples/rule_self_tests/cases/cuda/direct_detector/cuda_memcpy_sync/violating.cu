void demo(void* d, void* h) { cudaMemcpy(d, h, 64, cudaMemcpyHostToDevice); }
