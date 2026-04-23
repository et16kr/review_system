Django 서비스 검토 시 특히 아래를 중요하게 봅니다.

- DEBUG, csrf_exempt, raw/extra query 같은 trust-boundary 예외
- view, serializer, model 사이에서 validation ownership이 어디에 있는지
- ORM escape hatch가 parameterization과 contract clarity를 해치지 않는지
