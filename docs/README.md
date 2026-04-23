# Docs Index

이 디렉터리는 현재 구현을 설명하는 문서와 앞으로 할 일을 정리한 문서만 유지한다.
과거 설계 토론, 완료된 상세 설계, 요구사항 초안은 별도 archive 대신 Git history로 추적한다.

## Canonical Documents

- [CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1)
  - 현재 아키텍처, lifecycle, review-engine/rule 구조, adapter 상태, 데이터/KPI 모델
- [ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:1)
  - 앞으로 할 일, 우선순위, 완료된 작업과 더 이상 active가 아닌 작업
- [API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:1)
  - 현재 서비스 간 API와 adapter 계약
- [OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:1)
  - 로컬/운영 실행, GitLab smoke, migration, baseline, telemetry 절차
- [baselines/review_bot/](/home/et16/work/review_system/docs/baselines/review_bot/README.md:1)
  - review-bot 운영 baseline, wrong-language telemetry snapshot, backlog 템플릿

## Maintenance Rule

새 문서를 추가하기 전에 아래를 먼저 확인한다.

1. 현재 구조 설명이면 `CURRENT_SYSTEM.md`에 합친다.
2. 앞으로 할 일이면 `ROADMAP.md`에 합친다.
3. API contract면 `API_CONTRACTS.md`에 합친다.
4. 실행 절차나 smoke 명령이면 `OPERATIONS_RUNBOOK.md`에 합친다.

별도 문서는 새 API/DB/workflow/prompt contract처럼 독립적인 변경 축이 생길 때만 만든다.
