# Deferred Platform Expansion

## Purpose

이 문서는 현재 핵심 흐름과 별개인 SCM / platform 확장 작업을 모아 둔다.

마지막 코드 상태 점검일: `2026-04-24`

## 1. Multi-SCM Adapter Expansion

현재 미루는 이유:

- 지금은 `review-engine` gap 보강과 `review-bot` UX 개선이 더 작은 단위로 닫히고 효과도 즉시 확인된다.
- GitHub adapter는 설계/구현/smoke까지 한 번에 묶어야 해서 작업 단위가 크다.

착수 전 선행 조건:

1. 현재 GitLab lifecycle/schema 경계를 더 이상 흔들지 않을 정도로 안정화한다.
2. GitHub smoke 또는 replay fixture를 만들 테스트 리포지토리/권한 경로를 정한다.
3. `ReviewSystemAdapterV2` 경계에서 GitHub가 GitLab과 어떤 차이를 가질지 먼저 설계한다.
4. local harness의 current `ReviewRequestKey` 기반 bot bridge가 legacy `pr_id` endpoint와
   섞이지 않도록 먼저 정리한다.

착수 후 해야 할 일:

1. GitHub PR adapter를 `ReviewSystemAdapterV2`에 맞춰 설계한다.
2. metadata/diff/thread/status/check mapping을 구현한다.
3. GitHub smoke 또는 replay fixture를 최소 하나 만든다.
4. GitLab과 GitHub가 같은 lifecycle analytics schema를 공유하는지 검증한다.
5. GitHub 안정화 뒤 Gerrit patchset 모델을 별도 설계한다.

## Post-Review Boundary

`2026-04-24` 리뷰 라운드 기준으로 multi-SCM expansion은 계속 deferred다. GitHub/Gerrit 확장은
권한, fixture, adapter mapping, smoke 설계가 함께 필요해서 바로 수정할 항목이 아니다.

반대로 `review-platform` BotClient가 제거된 legacy `pr_id` bot endpoint를 호출하는 문제는
platform expansion이 아니다. 이것은 current local harness contract drift이므로 즉시 수정 항목으로
처리한다.
