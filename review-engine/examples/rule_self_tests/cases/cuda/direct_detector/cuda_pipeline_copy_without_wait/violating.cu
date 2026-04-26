void demo() { cuda::memcpy_async(block, dst, src, 16, pipe); compute_tile(); }
