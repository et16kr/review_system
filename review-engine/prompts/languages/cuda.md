CUDA 검토 시 특히 아래를 중요하게 봅니다.

- host/device 메모리 소유권과 해제 타이밍이 명확한지
- kernel launch, stream, synchronize 경계가 실패 처리와 함께 보이는지
- `__syncthreads`, shared memory, atomic 사용이 correctness 또는 hot-path 성능을 해치지 않는지
