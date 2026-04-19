# Self Code Review

날짜: 2026-04-19

대상 범위:

- `review-engine/`
- `review-platform/`
- `review-bot/`
- `ops/`

참고:

- 이 문서는 local harness 확장 단계의 self review 결과를 포함한다.
- 현재 운영 기준에서는 `review-platform/`을 canonical UI가 아닌
  로컬 데모/통합 테스트용 harness로 본다.

## 핵심 Findings

### 1. High

대상:
- [review_runner.py](/home/et16/work/review_system/review-bot/app/bot/review_runner.py:146)

문제:
- 봇이 댓글을 여러 개 게시하는 도중 중간 실패가 나면, 이미 외부 플랫폼에 게시된 댓글과
  내부 DB 상태가 불일치할 수 있었다.
- 이전 구현은 댓글 게시 루프가 끝난 뒤 한 번에 `commit()` 했기 때문에, 두 번째 댓글에서
  실패하면 첫 번째 댓글은 플랫폼에 남아 있지만 내부 publication 기록은 롤백될 수 있었다.

영향:
- 다음 리뷰 런에서 같은 finding을 중복 게시할 수 있었다.
- 게시 이력 추적이 깨질 수 있었다.

수정:
- 댓글 하나를 성공적으로 게시할 때마다 publication 상태를 즉시 `commit()` 하도록 변경했다.

상태:
- 해결 완료

### 2. High

대상:
- [review_runner.py](/home/et16/work/review_system/review-bot/app/bot/review_runner.py:42)
- [review_runner.py](/home/et16/work/review_system/review-bot/app/bot/review_runner.py:232)
- [review_runner.py](/home/et16/work/review_system/review-bot/app/bot/review_runner.py:267)

문제:
- 이전 구현은 파일 patch 전체를 한 번에 리뷰하고 첫 번째 hunk 라인 번호만 사용했다.
- 그래서 같은 파일 안에 동일 규칙 위반이 여러 hunk에 있어도 하나로 뭉개질 수 있었다.

영향:
- finding fingerprint가 과도하게 거칠어져, 여러 위치의 이슈가 하나로 dedupe 될 수 있었다.
- inline comment 위치 정확도도 낮았다.

수정:
- patch를 hunk 단위로 분리해서 리뷰하도록 변경했다.
- fingerprint에 `issue_signature`를 추가해 같은 규칙이라도 서로 다른 hunk/변경 패턴이면
  구분되도록 개선했다.

상태:
- 해결 완료

### 3. Medium

대상:
- [review_runner.py](/home/et16/work/review_system/review-bot/app/bot/review_runner.py:34)
- [review_runner.py](/home/et16/work/review_system/review-bot/app/bot/review_runner.py:279)

문제:
- 플랫폼 상태 업데이트 API 호출 실패가 리뷰 전체 실패로 이어질 수 있었다.
- 상태 표시는 보조 신호인데, 이 때문에 이미 finding 계산과 댓글 게시가 끝난 리뷰도 실패 처리될
  가능성이 있었다.

영향:
- 실제 리뷰 결과와 상태 표시가 불필요하게 불일치할 수 있었다.

수정:
- 상태 업데이트는 best-effort로 처리하는 `_safe_post_status()`를 추가했다.

상태:
- 해결 완료

## 추가 테스트

추가한 테스트:

- [test_review_runner.py](/home/et16/work/review_system/review-bot/tests/test_review_runner.py:138)
  - 같은 파일 내 multi-hunk 변경이 서로 다른 finding으로 유지되는지 검증
- [test_review_runner.py](/home/et16/work/review_system/review-bot/tests/test_review_runner.py:165)
  - 댓글 게시 도중 실패 시 이미 게시된 finding publication 상태가 유지되는지 검증

## 남은 리스크

아래는 아직 의도적으로 남겨 둔 항목이다.

1. `review-platform`은 아직 인증/권한 모델이 없다.
2. `review-platform`과 `review-bot`은 Postgres/Redis 연결이 들어갔지만 migration 체계는 아직 없다.
3. `review-bot`은 OpenAI structured output + stub fallback을 사용하지만, provider별 비용/지연 제어는 아직 얕다.
4. `review-engine`의 active/reference/excluded 분리는 완료됐지만, 운영 데이터 기준 더 촘촘한 규칙 큐레이션은 추가로 필요하다.
5. `review-platform` HTML UI는 MVP 수준이며 인증, reviewer assignment, merge workflow는 아직 없다.

## 결론

현재 self review 기준으로는, 새로 추가한 서비스들 중 가장 위험했던 부분은 `review-bot`의
게시 일관성과 finding granularity였다. 이 부분은 코드와 테스트로 보완 완료했다.
이후 남은 우선순위는 인증/권한, DB migration, 그리고 실제 내부망 배포 기준 운영 튜닝이다.
