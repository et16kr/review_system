__global__ void kernel() {}
void launch() { kernel<<<1, 32>>>(); }
