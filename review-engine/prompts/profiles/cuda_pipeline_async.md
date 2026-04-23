CUDA pipeline async 검토 시 특히 아래를 중요하게 봅니다.

- `cuda::memcpy_async`, `cp.async`, `__pipeline_memcpy_async` 뒤에서 staged tile의 첫 사용이 어떤 wait 또는 barrier phase 뒤에 오는지
- `producer_acquire`, `producer_commit`, `consumer_wait`, `consumer_release`가 부분 참여 분기 아래로 숨어 phase ownership을 흐리지 않는지
- `cuda::barrier` 또는 `mbarrier`가 shared staging buffer의 lifetime과 completion boundary를 로컬 코드에서 다시 읽을 수 있게 남겨 두는지
