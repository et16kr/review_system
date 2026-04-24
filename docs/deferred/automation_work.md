# Deferred Automation Work

## Purpose

이 문서는 auto-fix, approval, audit, rollback처럼 신뢰 경계가 중요한 자동화 작업을 모아 둔다.

마지막 코드 상태 점검일: `2026-04-24`

## 1. Review-Bot Apply / Auto-Fix Automation

현재 미루는 이유:

- roadmap 자체가 trust metric과 low-risk fix class를 선행 조건으로 요구한다.
- 지금 바로 자동 수정에 들어가면 false-positive, audit, rollback 경계가 불명확하다.

착수 전 선행 조건:

1. `fix_conversion_rate_28d`가 2 phase 이상 plateau인지 확인한다.
2. verify/ranking/provider tuning만으로 false-positive 저감이 정체인지 확인한다.
3. low-risk fix class를 충분히 좁게 정의한다.
4. reviewer approval, audit, rollback 정책을 먼저 문서화한다.
5. roadmap automation이 blocked unit을 retained artifact로 남기고, direct provider preflight가
   bounded runtime 안에서 끝나는지 먼저 확인한다.

착수 후 해야 할 일:

1. `@review-bot apply` 전에 low-risk fix class와 권한 모델을 정의한다.
2. patch 생성, audit, rollback, reviewer approval 경계를 설계한다.
3. provider `auto_fix_lines` payload를 실제 patch application flow와 연결할지 결정한다.
4. multi-reviewer parallel agent나 IDE 실시간 리뷰는 trust metric이 안정된 뒤 재평가한다.

## Post-Review Boundary

`2026-04-24` 리뷰 라운드 기준으로 auto-fix automation은 계속 deferred다. 신뢰 metric, low-risk
fix class, approval/audit/rollback 정책이 먼저 필요하다.

반대로 아래 automation guardrail은 auto-fix와 관계없이 즉시 수정할 항목이다.

- review-roadmap blocked unit을 `/tmp` scratch가 아니라 retained artifact로 남기는 것
- OpenAI direct smoke preflight에 timeout을 두어 automation loop가 멈추지 않게 하는 것

이 두 항목은 deferred automation의 선행 조건으로 기록하지만, auto-fix 설계가 시작될 때까지
미루지 않는다.
