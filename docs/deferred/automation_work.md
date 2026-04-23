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

착수 후 해야 할 일:

1. `@review-bot apply` 전에 low-risk fix class와 권한 모델을 정의한다.
2. patch 생성, audit, rollback, reviewer approval 경계를 설계한다.
3. provider `auto_fix_lines` payload를 실제 patch application flow와 연결할지 결정한다.
4. multi-reviewer parallel agent나 IDE 실시간 리뷰는 trust metric이 안정된 뒤 재평가한다.

## 2. Roadmap Automation Audit Artifact

현재 미루는 이유:

- blocked skip default 전략은 이미 유용하게 작동한다.
- 다만 반복 blocker를 roadmap 입력으로 쓰려면 영속적인 audit artifact가 필요하다.
- 이 작업은 자동화의 다음 정리 단계에서 묶는 편이 자연스럽다.

착수 전 선행 조건:

1. 어떤 수준의 artifact를 남길지 정한다.
   - latest markdown summary
   - append-only jsonl
   - baseline-style periodic snapshot
2. blocked reason taxonomy를 간단히 정한다.
   - credential
   - quota/billing
   - human review
   - local smoke env
   - ambiguous scope

착수 후 해야 할 일:

1. `advance_roadmap_with_codex.sh`가 blocked unit / reason / attempt / date를 영속 artifact로 남기게 만든다.
2. skip reason이 roadmap prioritization 입력으로 읽히도록 문서와 artifact 위치를 고정한다.
3. repeated blocker를 집계할 최소 운영 절차를 정한다.
