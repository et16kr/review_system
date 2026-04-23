CUDA Tensor Core 검토 시 특히 아래를 중요하게 봅니다.

- `wmma` 또는 `mma.sync` 경로가 warp-uniform collective 계약을 깨지 않는지
- inline PTX fast path가 tile shape, alignment, shared-memory staging 가정을 코드에서 드러내는지
- mixed-precision accumulation과 epilogue narrowing 경계가 숫자 계약과 함께 보이는지
