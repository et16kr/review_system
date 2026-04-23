CUDA TMA 검토 시 특히 아래를 중요하게 봅니다.

- `cp_async_bulk_tensor`, `cp.async.bulk.tensor`, `barrier_arrive_tx`, `mbarrier` 뒤에서 shared tile의 첫 사용이 어떤 wait 또는 barrier completion 뒤에 오는지
- `CUtensorMap`이 `__grid_constant__`, constant memory, 또는 global-memory + fence 중 어떤 경로로 전달되는지 로컬 코드에서 다시 읽을 수 있는지
- `tensormap_replace*` 뒤에 `tensormap_cp_fenceproxy` 또는 동등한 descriptor publication step이 남아 있어 이후 TMA 사용의 가시성이 보장되는지
