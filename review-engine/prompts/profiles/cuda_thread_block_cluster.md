CUDA thread block cluster 검토 시 특히 아래를 중요하게 봅니다.

- `__cluster_dims__` 또는 explicit cluster launch path가 kernel body의 `this_cluster()` 사용과 함께 로컬 코드에서 보이는지
- `cluster.sync()`나 cluster barrier가 block-rank, lane, partial participation 분기 아래로 숨어 collective contract를 흐리지 않는지
- `map_shared_rank()`로 얻은 distributed shared memory가 어떤 remote rank를 가리키고, 어떤 cluster-wide readiness boundary 뒤에서 접근되는지
