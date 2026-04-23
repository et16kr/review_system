Spring 백엔드 검토 시 특히 아래를 중요하게 봅니다.

- request, service, repository, transaction 경계가 뒤섞이지 않았는지
- field injection, broad repository reads, 설정 바인딩 검증 누락 여부
- DTO, validation, exception translation 책임이 어느 계층에 있는지
