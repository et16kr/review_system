CUDA async runtime 검토 시 특히 아래를 중요하게 봅니다.

- async API가 실제로도 explicit stream ownership 위에 서 있는지
- stream callback, event, graph capture가 버퍼 수명과 teardown을 숨기지 않는지
- overlap을 의도한 코드가 default stream ordering으로 다시 직렬화되지 않는지
