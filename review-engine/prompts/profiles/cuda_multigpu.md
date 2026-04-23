CUDA multi-GPU 검토 시 특히 아래를 중요하게 봅니다.

- `cudaSetDevice`와 per-device resource ownership이 ambient state에 기대지 않는지
- peer access와 peer copy가 topology/fallback 가정을 코드에서 드러내는지
- NCCL communicator, stream, collective ordering 계약이 로컬 코드에서도 읽히는지
