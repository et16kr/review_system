CUDA WGMMA 검토 시 특히 아래를 중요하게 봅니다.

- `wgmma.mma_async` issue가 lane/warp/warpgroup 분기 아래로 숨어 warpgroup-uniform participation을 깨지 않는지
- `wgmma.commit_group`, `wgmma.wait_group`, `wgmma.fence`가 어떤 participant set이 outstanding async MMA work를 닫는지 로컬 코드에서 다시 읽을 수 있는지
- accumulator 또는 epilogue narrowing이 `wgmma.wait_group` 뒤에 놓여, 결과 publication boundary가 로컬 패치에서 분명히 보이는지
