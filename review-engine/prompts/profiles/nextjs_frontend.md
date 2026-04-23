Next.js 프론트엔드 검토 시 특히 아래를 중요하게 봅니다.

- route handler, server action, client component가 각각 어떤 trust boundary인지
- `use client` 와 server default semantics가 섞이며 책임이 흐려지지 않는지
- request/form/env/cache 경계가 framework convenience 뒤에 숨지 않는지
