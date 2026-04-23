Tokio async 검토 시 특히 아래를 중요하게 봅니다.

- async 함수 안에서 blocking work가 executor를 잠식하지 않는지
- spawn, channel, cancellation에서 누가 lifecycle과 backpressure를 소유하는지
- panic/Result/unsafe boundary가 async 경계와 충돌하지 않는지
