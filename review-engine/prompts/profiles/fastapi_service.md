FastAPI 서비스 검토 시 특히 아래를 중요하게 봅니다.

- async request path 안에 blocking I/O가 숨어 있지 않은지
- request body가 typed model 대신 raw JSON으로 바로 소비되지 않는지
- dependency, background task, session lifetime 경계가 명확한지
