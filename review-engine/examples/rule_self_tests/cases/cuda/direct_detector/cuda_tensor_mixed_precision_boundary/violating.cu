void demo(float x) { wmma::mma_sync(acc, a, b, acc); __float2half_rn(x); }
