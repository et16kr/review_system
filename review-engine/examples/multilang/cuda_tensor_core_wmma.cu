#include <cuda_fp16.h>
#include <mma.h>

using namespace nvcuda;

__global__ void tensor_core_gemm(const half* a, const half* b, half* out, int lda, int ldb) {
    int lane = threadIdx.x % warpSize;

    wmma::fragment<wmma::matrix_a, 16, 16, 16, half, wmma::row_major> a_frag;
    wmma::fragment<wmma::matrix_b, 16, 16, 16, half, wmma::col_major> b_frag;
    wmma::fragment<wmma::accumulator, 16, 16, 16, float> acc_frag;

    if (lane == 0) {
        wmma::load_matrix_sync(a_frag, a, lda);
    }
    wmma::load_matrix_sync(b_frag, b, ldb);
    wmma::fill_fragment(acc_frag, 0.0f);
    asm volatile("mma.sync.aligned.m16n8k16.row.col.f32.f16.f16.f32");
    wmma::mma_sync(acc_frag, a_frag, b_frag, acc_frag);
    out[threadIdx.x] = __float2half_rn(acc_frag.x[0]);
}
