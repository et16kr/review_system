Go 검토 시 특히 아래를 중요하게 봅니다.

- error handling과 defer cleanup의 위치
- HTTP handler request decoding과 validation boundary
- context propagation과 goroutine lifetime
- request-scoped 작업이 실패/취소를 어떻게 전파하는지
