void demo(void* d, cudaStream_t stream) { float * host_buffer = malloc(64); cudaMemcpyAsync(d, host_buffer, 64, cudaMemcpyHostToDevice, stream); }
