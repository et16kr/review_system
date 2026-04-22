Rust 검토 시 특히 아래를 중요하게 봅니다.

- `unsafe` boundary의 범위와 invariant 설명
- `unwrap`/`expect`/`panic!`가 steady-state에서 허용되는지
- ownership과 error propagation이 API 계약에 맞는지
