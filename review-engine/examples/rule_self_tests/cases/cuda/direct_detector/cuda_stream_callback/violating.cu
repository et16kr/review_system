void demo(cudaStream_t stream, void* data) { cudaLaunchHostFunc(stream, callback, data); }
