CUDA Cooperative Groups 검토 시 특히 아래를 중요하게 봅니다.

- `tiled_partition` 같은 group 생성이 non-uniform branch 안으로 들어가 있지 않은지
- `grid.sync()`가 cooperative launch, residency, whole-grid participation 계약을 숨기지 않는지
- `group.sync()`가 rank- or lane-dependent control flow 아래에서 collective safety를 깨지 않는지
