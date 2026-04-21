# Review Bot Fundamental Review — Meta Evaluation

- 문서 상태: Assessment
- 작성일: 2026-04-21
- 작성자: Claude (본 문서의 1인칭은 원본 `REVIEW_BOT_FUNDAMENTAL_REVIEW.md`의 저자를 가리킨다)
- 대상 문서:
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW.md` (원본)
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_EVALUATION.md` (Codex의 원본 평가)
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_ENHANCED.md` (Codex의 보강본)

## 0. 이 문서를 왜 만드는가

`REVIEW_BOT_FUNDAMENTAL_REVIEW.md` 원본에 대해 Codex가 두 개의 문서로 리뷰를 회신했다.

- `EVALUATION.md`는 원본의 사실관계와 프레이밍을 지적한다.
- `ENHANCED.md`는 원본을 보정한 대체안을 제시한다.

두 문서의 지적이 모두 옳은지, 그리고 `ENHANCED.md`가 원본을 완전히 대체해도 되는지를
코드와 대조해 독립 판정한다.
이 문서의 결론은 다음 통합 문서(`REVIEW_BOT_FUNDAMENTAL_REVIEW_V2.md`)의 설계 근거가 된다.

## 1. 판정 요약

- `EVALUATION.md`의 5개 critique는 **코드로 모두 검증된다**. 수용해야 한다.
- `ENHANCED.md`는 원본의 **정당한 보정**이지만, **단독 대체는 권장하지 않는다**.
  구체 설계 해상도가 원본보다 낮다.
- 최적해는 **원본 + Evaluation 수정 + Enhanced의 Phase 0 / baseline-first 원칙을 병합**한 V2 문서다.

## 2. 사실관계 검증

Codex가 `EVALUATION.md`에서 제기한 주장을 코드와 직접 대조했다.

| 주장 | 검증 위치 | 판정 |
| --- | --- | --- |
| `Merge Request Hook`은 무시되고 note mention만 실제 리뷰를 트리거한다 | `review-bot/review_bot/api/main.py:191-197`에서 `manual_review_requires_bot_mention_comment`로 반환 | 맞음 |
| 테스트 SQLite는 이미 worker-scoped로 분리돼 있다 | `review-bot/tests/conftest.py:8-16`에서 `PYTEST_XDIST_WORKER` + `os.getpid()` 기반 파일 분리 | 맞음 |
| 원본이 `resolved_reason`으로 잘못 썼다 | 원본 149줄에서 `resolved_reason` 사용, 295/360줄에서는 `resolution_reason`. 실제 모델 필드는 `resolution_reason` (`db/models.py:186`) | 맞음 |
| summary note 자체는 이미 존재한다 | `review-bot/review_bot/bot/review_runner.py:2303` `_post_pr_summary` | 맞음 |
| 벤더 수치 대부분이 self-report다 | Diamond sub-3%, Bugbot 80% resolution rate 등은 모두 vendor 블로그 출처 | 맞음 |

→ 5개 critique는 모두 **코드 검증 통과**. 원본은 이 부분에서 오류 또는 stale 서술을 포함한다.

## 3. `EVALUATION.md` 자체 평가

### 3.1 잘한 점

- 증거 층위 구분(`code-verified` / `design-inference` / `market-informed`)이 유용하다.
  설계 문서 평가 방법론으로 재사용 가치가 있다.
- 5개 critique가 모두 근거 있는 현실적 지적이다.
- "원본 폐기 아님, 방향성은 유지, 실행 기준은 보강 필요"라는 최종 판정이 balanced하다.

### 3.2 불충분한 점

- Critique 스코프가 **표현 정확도 수준**에 머문다.
  원본의 핵심 주장(verify phase 우선 / severity-score 분리 / context graph 확장 순서)에 대한
  **반박이나 대안 우선순위 제시는 없다**.
- **원본이 *누락한 것*에 대한 지적이 약하다.**
  예: Ellipsis식 병렬 generator + filter pipeline은 false-positive 저감의 핵심인데
  원본도 Phase D로 밀어 뒀고, Evaluation도 이 점을 건드리지 않는다.
- **벤더 수치 critique가 일반론적**이다.
  "KPI 직접 근거로 쓰지 말라"는 원칙은 옳지만, 방향성 신호로서의 가치는 남는다.
  Evaluation은 이 구분을 약하게 한다.

## 4. `ENHANCED.md` 자체 평가

### 4.1 강점

- **Phase 0 신설**(트리거 모델 + `resolution_reason` 체계 + 측정 규칙)은 정당한 개선이다.
  원본이 암묵적으로 전제하던 사항을 문서 앞으로 끌어냈다.
- **baseline-first 원칙**(`2주 baseline 측정 → baseline 대비 개선폭으로 목표 설정`)은
  원본의 약점을 정확히 보완한다.
  원본이 Bugbot 80%를 "북극성"으로 배치한 것은 실제로 과욕이었다.
- **run summary vs walkthrough 분리.** 원본의 "요약 없음" 표현을
  "run summary는 있지만 walkthrough 역할은 못 한다"로 정확히 재서술.
- **점진적 migration 원칙.** `.review-bot.yaml`을 "기능 확장"이 아니라 "설정 수렴"으로
  재정의한 것은 실행 위험을 낮추는 현실적 판단.
- **field naming 일관**: `resolution_reason`으로 통일.
- **Defer 목록의 근거 명시**: cross-repo / multi-lang / IDE / multi-agent를
  "acceptance baseline 확보 전까지 후순위"로 분명히 함.

### 4.2 약점

- **구체성이 후퇴했다.**
  원본 §6에 있던 verify phase flow 의사코드, `.review-bot.yaml` 전체 스키마 예시,
  walkthrough 노트 포맷 샘플이 Enhanced에서 모두 사라졌다.
  설계 문서로서는 해상도가 낮아졌다. "보강"보다 "요약"에 가깝다.
- **코드 참조 손실.** 원본은 부록 A에 `review_runner.py:<line>` 인용을 집중 정리했다.
  Enhanced는 `review_bot.bot.review_runner._current_backlog_entries` 수준의 상징 참조 몇 개만 남음.
  구현자 관점에서 "어디를 고치면 되나" 찾기 어려워진다.
- **Phase 0를 "0–2주"로 박은 것은 과잉 설계 가능성.**
  `P0.1 trigger model 명시`는 회의 한 번에 결정될 정책 사안이지 2주짜리 phase가 아니다.
  `P0.2 resolution_reason 체계 확장`은 Phase A1과 거의 동일한 작업이라 분리 실익이 적다.
  Phase 0는 사실상 "P0.3 측정 규칙 문서화" 하나면 충분하다.
- **baseline 측정 방법은 비어 있다.**
  "2주간 baseline 측정"이라고 썼지만 어떤 쿼리로 / 어떤 대시보드로 / 누가 집계하는지가 없다.
  baseline-first 원칙을 주장했으면 이 부분이 가장 구체적이어야 한다.
- **C2 similarity-based suppression이 원본보다 후퇴.**
  원본은 Ellipsis embedding 유사도 접근을 인용하며 초기(문자열 유사도) → 후속(vector index) 경로를 제시.
  Enhanced는 한 문단으로 뭉갰다.
- **multi-reviewer 병렬화(D3) 후순위 판단의 근거가 약하다.**
  "현재 단계에선 과투자 가능성이 높다" 한 줄.
  Ellipsis는 이 병렬 구조가 false-positive 저감의 핵심이라고 주장하므로
  단순 "과투자"로 치부하기엔 근거가 부족하다.
  Enhanced 자신의 "verify 우선"과도 긴장 관계(병렬 generator도 verify 전략의 일부).
- **KPI 정의는 들어왔지만 instrumentation이 없다.**
  §6.1 KPI 이름만 있고, 어느 메트릭에서 파생되는지 / Prometheus label / 대시보드 올리는 방법은 없다.

## 5. 원본 재평가

Evaluation / Enhanced를 모두 읽은 뒤 원본을 다시 보면:

- **방향성 판단은 유효.** Codex도 "핵심 구조 진단과 큰 방향은 꽤 잘 맞는다"고 인정.
- **표현 정확도와 사실 fresh함은 약했다.** 특히 SQLite 현황과 필드명 (`resolved_reason` vs `resolution_reason`).
- **벤더 수치를 KPI 목표로 사용한 것은 실수.** Bugbot 80%를 "북극성"으로 박으면 내부 baseline 없이 목표가 고정된다.
- **트리거 모델 전제를 암묵 처리한 것도 실수.** walkthrough 자동 게시, acceptance freshness는 모두 트리거 모델에 의존.

반면 원본의 **구체적 설계 스케치(verify flow / yaml 예시 / walkthrough 포맷 / 코드 참조 부록)는
Enhanced가 대체하지 못한 가치**다. 구현자 관점에서 원본의 이 섹션들은 유지되어야 한다.

## 6. 결론: V2 문서 병합 원칙

V2 문서는 아래 병합 원칙을 따른다.

1. **원본 기본 골격 유지** — Executive Summary, 지형도, 업계 비교, 유지/재검토 구분, §6 상세 설계.
2. **Evaluation의 5개 critique를 본문에 반영**:
   - `resolved_reason` → `resolution_reason` 전수 교체
   - 테스트 SQLite 섹션 삭제 (또는 "해결됨" 각주)
   - "walkthrough 부재" → "walkthrough 역할을 하는 summary 없음"
   - 벤더 수치에 **market-informed** 태그를 병기
   - 트리거 모델(Note Hook mention driven)을 §1에서 명시적으로 선언
3. **Enhanced의 Phase 0 신설 정신 수용**, 단 2주 phase로 박지 말고
   **"Phase A 시작 전 결정해야 할 pre-check 목록"**으로 구조 변경.
4. **Enhanced의 baseline-first 원칙 수용**. KPI 절을 "목표치"보다 "baseline 측정 방법 + 개선폭"으로 재작성.
   원본의 80% 같은 외부 수치는 *참고 대역*으로만 남긴다.
5. **원본의 verify phase 의사코드 / `.review-bot.yaml` 예시 / walkthrough 포맷 / 코드 참조 부록 유지**.
6. **Evaluation이 놓친 "원본이 누락한 것"도 본문에 반영**:
   - Ellipsis 병렬 generator + filter pipeline 논점을 Phase C 혹은 D의 판단 포인트로 명시
   - multi-reviewer 병렬화의 defer 근거를 "현 단계 과투자"가 아닌 "acceptance baseline 확립 후 비용-효과 재평가"로 재서술
7. **KPI instrumentation을 명시** — Prometheus metric 이름 / label / 어느 파일에서 증설하는지 / 대시보드 구성.

위 원칙을 반영한 산출물이 `REVIEW_BOT_FUNDAMENTAL_REVIEW_V2.md`다.

## 7. 산출물 구성

이 meta evaluation의 결과로 아래 파일 구성을 제안한다.

| 문서 | 상태 | 역할 |
| --- | --- | --- |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW.md` | 유지 (archival) | 1차 설계 메모, 토론 이력 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_EVALUATION.md` | 유지 (archival) | Codex 평가 이력 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_ENHANCED.md` | 유지 (archival) | Codex 보강본 이력 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_META_EVALUATION.md` | 본 문서 | Codex 두 문서의 독립 판정 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_V2.md` | 신규 (current) | 실행 기준 통합 문서 |

V2 이후의 변경은 V2 파일에서 이어간다. 앞선 3개 문서는 변경하지 않고 이력으로 남긴다.
