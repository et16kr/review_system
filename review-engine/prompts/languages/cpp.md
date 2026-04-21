C++ 검토 시 특히 아래를 중요하게 봅니다.

- RAII와 표준 라이브러리 기반 자원 관리
- raw pointer, 수명, 소유권, 예외/조기 반환 경로
- switch/loop 같은 제어 흐름의 명확성
- 형식 안전성, portability, low-level API 캡슐화
- printf 계열보다 더 안전한 typed I/O와 formatting 방향
