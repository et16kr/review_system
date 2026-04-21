# 리뷰 봇 근원 점검 및 개선 방향 보고서 (V2, 통합판)

- 문서 상태: Current — 실행 기준 문서
- 작성일: 2026-04-21
- 작성자: Claude (병합 작업)
- 관련 문서:
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW.md` (원본, archival)
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_EVALUATION.md` (Codex 평가, archival)
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_ENHANCED.md` (Codex 보강본, archival)
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_META_EVALUATION.md` (본 V2의 병합 근거)

## 0. 이 문서를 왜 만드는가

`REVIEW_BOT_FUNDAMENTAL_REVIEW.md` 원본은 방향성 메모로는 적절했지만,
사실관계(필드명, 테스트 SQLite 현황), 트리거 모델 전제, 벤더 수치 취급에서 보정이 필요했다.
Codex의 `EVALUATION.md`와 `ENHANCED.md`는 각각 유효한 지적과 부분적 대체안을 제시했지만,
어느 쪽도 단독으로 실행 기준 문서가 되기 어려웠다.

- Evaluation은 critique만 담았다.
- Enhanced는 구조는 잡았지만 구체 설계 해상도가 원본보다 낮았다.
- 원본은 해상도는 높았지만 5가지 오류/누락을 가지고 있었다.

V2는 이 세 문서를 병합해 **한 파일만 읽고도 설계/구현/측정 기준을 잡을 수 있게** 한다.
판단 근거는 `REVIEW_BOT_FUNDAMENTAL_REVIEW_META_EVALUATION.md`의 §6 병합 원칙에 따른다.

> 이후 변경은 본 V2 파일에서 이어간다. 앞선 세 문서는 이력으로 남긴다.

## 1. Executive Summary

현재 `review-bot`은 "inline-first, lifecycle-aware, feedback-aware" 봇으로서
**골격은 잘 잡혀 있다**. `detect -> publish -> sync` 파이프라인, fingerprint 기반 dedupe,
`ThreadSyncState` 기반 backlog, thread reply 기반 feedback 해석,
명시적 command 파서, current-state backlog view는 업계 상위권 봇과 같은 방향이다.

다음 투자 우선순위는 아래 순서다.

1. **트리거 모델 / 측정 전제 확정** (pre-check, 결정 작업)
2. **신뢰도 강화** (verify phase, severity/score 분리, acceptance tracking)
3. **context 강화** (syntax-aware split, 관련 파일 retrieval)
4. **학습 + UX** ((project, rule) weight, walkthrough, ask)
5. **자동화 확장** (apply, 접힘 모드, 필요 시 병렬 reviewer)

핵심 메시지는 두 가지다.

- 지금 필요한 것은 "더 많이 지적하는 봇"이 아니라
  **"더 믿을 수 있고, 더 맥락을 알고, 더 실행 가능한 제안을 하는 봇"**이다.
- 외부 벤더 수치(Bugbot 80%, Diamond sub-3% 등)는 방향성 신호일 뿐이며,
  **내부 목표는 반드시 내부 baseline 측정 후 baseline 대비 개선폭으로 정의**한다.

## 2. 증거 층위 규칙

이 문서의 주장은 세 층위로 태그한다.
독자가 "확인된 사실"과 "외부 참고치"를 같은 무게로 읽지 않게 한다.

- `[code-verified]` — 현재 저장소 코드와 대조 가능
- `[design-inference]` — 코드와 구조로 해석 가능하나 설계자 의도 추론 포함
- `[market-informed]` — 외부 제품 문서/블로그/벤더 주장 (vendor self-report 포함)

명시적 태그가 없는 서술은 기본적으로 `[design-inference]`로 간주한다.

## 3. 현재 시스템 지형 (code-verified)

### 3.1 트리거 모델 — 전제 명시

현재 `review-bot`은 **"Note Hook mention 기반 수동 호출형 리뷰어"**다.

- `[code-verified]` `Merge Request Hook`은 `manual_review_requires_bot_mention_comment`로
  명시적 무시됨 (`review-bot/review_bot/api/main.py:191-197`).
- `[code-verified]` `POST /webhooks/gitlab/merge-request`가 `Note Hook`일 때만
  `_handle_gitlab_note_hook`로 진입 (`api/main.py:189-190`).
- `[code-verified]` 실제 review run 생성은 `create_review_run_for_key` 호출로 일어나며,
  호출 경로는 내부 API(`POST /internal/review/runs`)와 note mention 두 가지뿐.

이 전제는 walkthrough 자동 게시, acceptance tracking freshness,
sync phase 실행 주기의 설계 선택에 직접 영향을 준다.
V2는 이 전제를 **유지하는 것을 기본으로 하되, Phase C에서 optional auto-trigger 도입 여부를 재평가**한다.

### 3.2 파이프라인 개요

```
GitLab Note Hook
     │
     ▼
[ Webhook API (rate limit, explicit command parser) ]
     │  review / full-report / backlog / help
     ▼
[ Detect Queue ] ──► EngineClient (/review/diff, top_k, circuit breaker)
     │                      ▲
     │                      └── RAG: search_codebase(top_k=2) + file_context(4000자)
     ▼
[ FindingEvidence + FindingDecision 생성 ]
     │  - fingerprint = hash(key, file, line, human_key, issue_signature)
     │  - score = raw × rule_weight - penalties + policy_adjustment
     │  - state = eligible | suppressed | ...
     ▼
[ Publish Queue ] ──► Adapter.upsert_comment / resolve_thread
     │  - dedupe by (file, line, rule) per batch
     │  - inline anchor 실패 → suppressed (inline_anchor_unavailable)
     │  - body_hash 동일 open thread → 건너뜀 (batch slot 소비 X)
     ▼
[ Sync Queue ] ──► ThreadSyncState reconcile
     │  - resolution_reason: remote_resolved / no_longer_eligible / anchor_changed
     │  - feedback 커맨드 ingest (bot:ignore / false-positive / later / allow)
     ▼
[ 일반 노트 ] run summary + (on demand) full-report / backlog / help
```

세부: `review-bot/review_bot/bot/review_runner.py`, `api/main.py`, `review_systems/gitlab.py`.

### 3.3 현재 강점 (code-verified)

- **Inline-first**: canonical UI는 GitLab discussion thread.
- **Lifecycle 분리**: detect / publish / sync가 별도 queue로 실패 국소화.
- **Thread sync 상태 모델**이 명확: open / resolved / stale / remote_reopened.
- **Feedback-aware**: `bot:ignore`, `bot:false-positive`, `bot:later`, `bot:allow`가
  thread reply 수준에서 해석됨 (`review_runner.py:1768` 부근 `_latest_feedback_command`).
- **Dedupe 이중화**: fingerprint(동일 finding) + anchor_signature(thread identity).
- **Policy hook**: path별 score_adjustment, minimum_score, suppress/promote (`policy.py`).
- **Rule learning 시그널**: 인간 resolve 비율 기반 rule 가중치, distinct fingerprint 단위로 집계
  (`review_runner.py::_load_rule_effectiveness_weights`).
- **Current-state backlog view**: 최근 개편으로 `ThreadSyncState` 기반 backlog 렌더링.
- **보수적 command parser**: 줄 시작 mention만 인식, unknown token은 ignore.
- **테스트 DB 분리** `[code-verified]`: worker-scoped SQLite 파일 분리
  (`tests/conftest.py:8-16`, `PYTEST_XDIST_WORKER + os.getpid()`).
  → 원 원본이 지적한 "공유 SQLite" 문제는 이미 해결됨.

### 3.4 현재 한계 (code-verified / design-inference)

- `[code-verified]` context가 현재 파일의 앞 4000자에 국한 (`FILE_CONTEXT_MAX_CHARS`).
- `[design-inference]` diff 분할이 lexical(80 라인 hunk). 함수/블록 경계를 보지 않음.
- `[design-inference]` 검증 phase 부재 — 엔진+LLM 제안이 그대로 게시.
- `[code-verified]` severity가 score의 파생값: `_severity_from_score(score) → low/medium/high`.
- `[code-verified]` rule 가중치가 `rule_no` 단위 global. project별 분리 없음.
- `[design-inference]` acceptance(실제 코드 수정 유발 여부) 측정 없음.
- `[code-verified]` `auto_fix_lines` 필드는 있으나 commit/branch 자동화 루프 없음.
- `[code-verified]` `@review-bot summarize` / `ask` / `apply` 같은 interactive command 없음.
- `[code-verified]` 설정 표면이 `policy.json + env var`로 분산.
- `[code-verified]` rate limit이 process-local `deque` (`main.py:34` 주석도 이미 경고).
- `[code-verified]` run summary note는 존재하지만(`_post_pr_summary`, `review_runner.py:2303`)
  **"요약이 없다"가 아니라 "walkthrough 역할을 하는 summary는 없다"**.
  현재 summary는 게시된 finding 수 요약에 가깝고, 변경 요지/영향 symbol/주목 finding은 담지 않는다.

## 4. 업계 Reference 비교

> 이 절의 수치는 `[market-informed]`이며 대부분 vendor self-report다.
> 방향성 신호로만 사용한다. KPI 목표의 직접 근거로는 사용하지 않는다 (§8 참조).

### 4.1 비교 대상

| 봇 | 특징 요약 |
| --- | --- |
| CodeRabbit | massive codebase 지원, walkthrough + sequence diagram, Learnings, `.coderabbit.yaml` |
| Greptile | code graph 기반 multi-hop, embedding 기반 코멘트 품질 개선 사례 |
| Graphite Diamond | 자체 PR 데이터로 eval set 구축, 수락률을 KPI로 사용 |
| Cursor Bugbot | multi-pass agentic verification, learned rules, autofix |
| Ellipsis | 병렬 comment generator + multi-stage filtering pipeline, thumbs embedding 학습 |
| Qodo Merge (ex PR-Agent) | 풍부한 slash command(`/review`, `/describe`, `/improve`, `/ask`), auto best practices |
| Sourcery | 다중 AI reviewer + 정적 분석, `.sourcery.yaml` |
| GitHub Copilot Review | `.github/copilot-instructions.md`, agentic tool calling |

### 4.2 핵심 특성 비교

| 항목 | 현재 `review-bot` | CodeRabbit | Greptile | Diamond | Bugbot | Qodo |
| --- | --- | --- | --- | --- | --- | --- |
| inline comments | O | O | O | O | O | O |
| PR walkthrough (변경요지/영향/주목) | 요약 노트만 | O (diagram 포함) | O | O | O | `/describe` |
| sequence diagram | X | O | - | - | - | - |
| 자연어 chat(`ask`) | X | O | O | - | - | `/ask` |
| multi-pass 검증 | X | O (일부) | O | O | O (핵심) | - |
| codebase graph | X | O | O (코어) | O | - | - |
| per-repo learned rules | rule-level 가중치 | Learnings | vector embedding | eval dataset 기반 | learned rules | auto best practices |
| slash/mention command | O (review/full-report/backlog/help) | O | O | O | O | 풍부 |
| autofix(commit) | 필드만 | O (pro) | - | - | O | - |
| multi-repo / cross-repo | X | O | O | - | - | - |
| config file | env + policy.json | `.coderabbit.yaml` | UI | UI | UI | `.pr_agent.toml` |

### 4.3 업계 수렴 패턴

1. **flag → verify → post** 3단 구조 — Bugbot multi-pass, Ellipsis multi-stage filter, CodeRabbit "receipts".
   공통 메시지는 *모델을 믿지 말고 증거를 요구하라*.
2. **Learned rules / knowledge base** — feedback을 프롬프트에 직접 밀어넣기보다
   유사 코멘트 embedding / rule로 규범화. Greptile의 few-shot 실험은 오히려 악화 보고.
3. **severity는 정책으로 다룬다** — critical/warning/suggestion/nitpick 분리.
   suggestion 이하는 접어서 노이즈 감소.
4. **Walkthrough는 별도 산출물** — 라인 코멘트와 별개로 "이 MR이 무엇을 바꾸는가" 산출.
5. **수락률(acceptance rate)을 1급 KPI로** — Diamond 사례. comment count가 아니라 실제 반영된 비율.
6. **auto-fix는 검증된 경우에만** — Bugbot은 build verification 후 commit. merge 결정은 사람이.
7. **설정은 repo 안 yaml** — `.coderabbit.yaml`, `.sourcery.yaml`, `.pr_agent.toml`,
   `.github/copilot-instructions.md`.

## 5. Gap 분석

### 5.1 신뢰도 (Must-fix)

**5.1.1 수락률이 측정되지 않는다**
- 현재 `/internal/analytics/rule-effectiveness`는 resolve_rate / human_resolve_rate를 제공하나,
  "실제로 코드 수정이 있었는가"는 미측정.
- `ThreadSyncState.resolution_reason`을 확장해 `fixed_in_followup_commit` /
  `remote_resolved_manual_only`를 구분해야 한다.
  (Bugbot의 resolution rate 방식을 차용 `[market-informed]`.)

**5.1.2 검증 phase 부재**
- 업계 공통 해법은 엔진 결과에 대해 별도 agent가 증거 재검증.
- 두 가지 모드 병행 권장:
  - (a) rule-execution 검증: 패턴 기반 finding은 regex/AST로 재확인.
  - (b) LLM self-check: 저확신도 finding은 추가 LLM 호출로 재평가.

**5.1.3 severity = f(score) 문제**
- `_severity_from_score`는 fallback일 뿐, severity는 provider/engine의 자기주장을 보존해야 한다.
- 층위는 `nitpick / suggestion / warning / critical`.
- 기존 `low/medium/high`는 호환 alias로 유지.

### 5.2 Context / Retrieval (High)

**5.2.1 단일 파일 context**
- `file_context` 4000자 제한. 호출부/정의부가 다른 파일일 때 놓침.
- 점진 경로:
  1. touched symbol 기준 1-hop 정의/참조 파일 excerpt 주입.
  2. finding 단위 second retrieval — 각 finding의 title+summary로 mini-query.
  3. 중장기: diff-level retrieval vs finding-level retrieval을 구조적으로 분리.

**5.2.2 review unit이 lexical**
- 80라인 hunk split을 함수/블록 경계 기반으로 교체.
- C/C++에 한해 tree-sitter 기반 함수 단위 split 먼저 도입 (`CPP_EXTENSIONS` 범위).

### 5.3 Learning (High)

**5.3.1 학습 단위가 rule 전체**
- `(project_ref, rule_no)` 단위로 확장.
- 적은 트래픽 rule은 Bayesian smoothing으로 보정(5건 임계 제거).

**5.3.2 유사도 기반 suppression**
- Ellipsis 방식 `[market-informed]`: 과거 ignore/false-positive 받은 finding과
  신규 finding의 embedding 유사도가 높으면 pre-publish에서 suppress.
- 초기: 제목+요약의 문자열 유사도(`difflib`) 정도로도 유효 신호 잡힘.
- 이후: vector index (in-process FAISS 규모면 충분).

### 5.4 Output UX / Actionability (High)

**5.4.1 walkthrough 역할 분리**
- 현재 `_post_pr_summary`는 **run summary**(이번 배치 게시 항목 요약) 성격.
- **walkthrough**(MR onboarding: 변경 요지 / 영향 symbol / 주목 finding)는 별도 산출물로 정의.
- 두 개를 분리해야 요구사항이 엇갈리지 않는다.

**5.4.2 제안이 "읽을 것"에 그침**
- suggestion block 확신도 ≥ 0.9 && 교체 라인 ≤ 5인 경우에만 노출 (보수적).
- `@review-bot apply <thread-ref>`: 별도 branch 생성 → patch → **build/lint 검증 후** push.
- merge는 사람이.

**5.4.3 chat 부재**
- `@review-bot ask <질문>` 추가. thread + diff + 관련 파일 excerpt를 LLM에 위임.
- 동일 thread 안에서 3턴 유지.

### 5.5 운영 / 신뢰성 (Medium)

- `[code-verified]` rate limit이 process-local. Redis sliding window로 교체.
- 설정 표면 수렴: `.review-bot.yaml`을 도입하되 **기능 확장이 아니라 설정 수렴**.
  `policy.json`은 유지하고 우선순위 규칙만 명확히 해 점진 이행.

### 5.6 Observability (Medium)

- 추가 메트릭:
  - `review_comments_resolved_total{resolution_reason, rule_no}`
  - `review_comments_acceptance_rate{window="7d", project}` (파생)
  - `review_feedback_commands_total{command}`
  - `verify_phase_drop_total{reason}` (verify phase 도입 시)

### 5.7 장기 / Defer

- `[design-inference]` cross-repo analysis, multi-lang 대확장, IDE 실시간 리뷰는
  **acceptance baseline이 확보되기 전까지 후순위**.
- **multi-reviewer 병렬화(Ellipsis 방식)**는 원본이 defer, Enhanced도 defer.
  단순 "과투자" 치부가 아니라 **Phase A/B에서 verify + context 개선 후**에
  "병렬 generator의 한계 비용/효과"를 실측해 재평가한다.
  verify phase의 자연스러운 확장 경로이므로 폐기가 아닌 "조건부 defer"다.

## 6. 유지 / 재검토 판정

### 6.1 유지할 결정

- inline-first review UX.
- detect / publish / sync 분리.
- fingerprint + anchor_signature 이중 dedupe.
- feedback command를 thread reply에서 해석하는 방식.
- `ThreadSyncState` 기반 backlog / analytics.
- path policy 기반 score 조정과 suppress/allow.

### 6.2 재검토할 결정

- `severity = f(score)` (→ provider가 severity를 보유하도록).
- `rule_no` global weight (→ `(project_ref, rule_no)` 단위).
- note-only trigger 유지 vs 자동 기능 확장 (→ Phase C에서 재평가).
- summary append-only vs same-purpose upsert.
- `policy.json + env` 분산 설정.

## 7. Phase 0 — Pre-check (결정 작업)

> Enhanced의 Phase 0 신설 정신을 수용하되, **2주 implementation phase가 아니라
> Phase A 시작 전 확정해야 할 결정 목록**으로 축소한다.
> 회의 1–2회 수준에서 끝나는 것이 정상이다.

### P0.1 트리거 모델 결정

- 질문: MR hook을 (a) 계속 무시 / (b) metadata refresh + sync 전용으로 부분 도입 /
  (c) 자동 review까지 확장 — 셋 중 어디로 갈 것인가.
- 권장 default: (a) 유지. walkthrough 자동 게시가 필요해지는 시점에 (b)로 확장.
- (c)는 acceptance baseline 확보 전까지 금지.

### P0.2 `resolution_reason` 체계 확정

- 현재 값: `remote_resolved`, `no_longer_eligible`, `anchor_changed`.
- 추가 후보: `fixed_in_followup_commit`, `remote_resolved_manual_only`.
- 구현은 Phase A1과 합친다. 여기서는 **명칭과 의미**만 확정하면 된다.

### P0.3 측정 규칙 확정

- acceptance / ignore_rate / signal_ratio / verify_drop_rate 정의를 먼저 고정.
- baseline 측정 방법(§8) 동의.
- 이후 단계별 목표는 "절대 수치"가 아닌 "baseline 대비 개선폭"으로 고정.

## 8. KPI 및 Baseline 측정 (baseline-first)

### 8.1 baseline 측정 절차 (2주)

1. 현 analytics 엔드포인트와 새 metric을 최소한으로 추가해 지표 수집 시작.
2. 2주간 실제 운영 데이터로 아래 분포 관측:
   - published / resolved / suppressed의 ratio
   - `resolution_reason` 분포 (remote_resolved vs no_longer_eligible)
   - `bot:ignore` / `bot:false-positive` / `bot:later` / `bot:allow` 빈도
   - inline_anchor_unavailable 등 게시 실패 분포
3. baseline을 숫자로 기록. 이후 Phase A 이상 목표는 이 기록 대비 변화량으로 정의.

### 8.2 최소 KPI와 instrumentation

| 이름 | 정의 | 파생 기반 metric |
| --- | --- | --- |
| `acceptance_rate` | 실제 fix 근거 확인된 해결 비율 | `review_comments_resolved_total{resolution_reason="fixed_in_followup_commit"}` / `review_comments_resolved_total` |
| `signal_ratio` | warning 이상 비중 | `review_comments_posted_total{severity="warning|critical"}` / `review_comments_posted_total` |
| `ignore_rate` | ignore/false-positive 누적 / published | `review_feedback_commands_total{command="ignore|false-positive"}` / `review_comments_posted_total` |
| `verify_drop_rate` | verify stage drop / verify 대상 | `verify_phase_drop_total` / `verify_phase_attempt_total` |

- Prometheus metric 정의 위치: `review_bot.metrics`.
- label 설계:
  - `resolution_reason`, `rule_no`, `severity`, `command`, `reason`.
  - cardinality 폭발 방지를 위해 `rule_no`는 top-N만, 나머지는 `__other__`.
- 대시보드: Grafana `review-bot/overview`에 `acceptance_rate`, `signal_ratio`, `ignore_rate`를 패널화.

### 8.3 해석 규칙

- **`resolved`는 acceptance가 아니다** (`remote_resolved`만으로는 수정 증거 아님).
- **`suppressed` 감소만으로 성공 판단 금지**.
- **published count 증가는 성공 지표가 아니다**.
- **baseline 없는 목표 수치는 문서에 고정하지 않는다**.

### 8.4 시장 참고치 (KPI 목표 아님)

`[market-informed]`:

- Diamond: false positive < 3% (vendor self-report, 2026).
- Bugbot: resolution rate ~80% (vendor blog, 2026).
- Greptile: addressed comments 19% → 55% 개선 사례.

내부 목표는 위 수치를 직접 차용하지 않는다.
"baseline 대비 20–30% 개선"이 현실적 1차 목표다.

## 9. 강화된 로드맵

> Phase 기간은 예시이며 team velocity에 맞춰 조정한다.
> **Phase 0는 결정 작업이지 implementation phase가 아니다**.

### Phase A (2–4주) — 신뢰도

- **A1. Acceptance tracking**
  - sync phase에서 thread가 `resolved`로 transition될 때 이후 commit diff를
    `file_path ± 3 lines` 범위로 조회.
  - 변화 있으면 `resolution_reason=fixed_in_followup_commit`,
    없으면 `remote_resolved_manual_only`.
  - 참고 구현: `review_runner.py`의 sync phase hooked helper.
- **A2. Severity / Score 분리**
  - `FindingDecision.severity`는 provider/engine이 자기주장한 값을 저장,
    `_severity_from_score`는 fallback only.
  - 새 층위: `nitpick / suggestion / warning / critical`. `low/medium/high`는 alias.
- **A3. Verify phase (optional) 도입**
  - env `BOT_VERIFY_WITH_LLM_CONFIDENCE=0.85`.
  - `_build_decision` 직후, 확신도 임계 이하 finding을 LLM self-check에 위임.
  - drop 이유는 `verify:llm_self_check` / `verify:low_confidence` 네임스페이스.
- **A4. Distributed rate limit**
  - `api/main.py`의 per-IP deque를 Redis-backed sliding window로 교체.
- **A5. Metrics 보강**
  - 위 §8.2 표의 metric을 Prometheus에 선언.
  - Grafana 대시보드 패널 구성.

### Phase B (4–8주) — Context

- **B1. Syntax-aware review unit split**
  - `_iter_review_units`를 tree-sitter 기반으로 확장. C/C++ 먼저.
  - hunk가 함수 하나보다 작으면 함수 body 전체를 review_unit.patch로.
- **B2. Related file retrieval**
  - touched symbol 기준 정의/참조 1-hop excerpt를 engine payload `file_context`에 병합.
  - `primary_file_context + related_contexts` 구조화.
- **B3. Finding-level second retrieval (optional)**
  - 각 finding의 title+summary로 `search_codebase` 재호출.
  - 유사 과거 finding의 accept/ignore 통계를 hint로 프롬프트에 포함.

### Phase C (8–12주) — 학습 + UX

- **C1. `(project_ref, rule_no)` weight**
  - `_load_rule_effectiveness_weights(scope=(project, rule_no))` 시그니처 확장.
  - 5건 임계 대신 Bayesian smoothing.
- **C2. Similarity-based learned suppression**
  - 초기: (title + summary + file_path) 문자열 유사도(`difflib`) ≥ 0.9면 pre-publish에서
    `suppressed(reason=learned:similar_ignore)`.
  - 후속: in-process FAISS embedding index. 규모 확인 후 도입.
- **C3. `.review-bot.yaml` 도입** (설정 수렴)
  - 스키마 예시는 §11.3.
  - `policy.json`과 env를 대체하지 않고 **우선순위 규칙**만 확정.
- **C4. Walkthrough note**
  - 1차: on-demand `@review-bot summarize`.
  - 2차: optional MR 오픈 시 auto-post (P0.1이 (b)로 확장된 경우만).
  - run summary와 **다른 purpose**로 `upsert_general_note(purpose="walkthrough")`.
- **C5. `@review-bot ask <질문>`**
  - thread context + diff + 관련 파일 excerpt 기반 답변. thread reply로 게시.
  - history 3턴.

### Phase D (12주+) — 자동화 확장

- **D1. `@review-bot apply`**
  - 확신도 ≥ 0.9 + suggestion 라인 ≤ 5 + build/lint pass 조합에서만 허용.
  - branch 생성 → patch → push. merge는 사람이.
- **D2. Collapsed low-priority output**
  - `nitpick` / `suggestion`은 GitLab `<details>` 접힘 블록으로.
- **D3. (조건부) Multi-reviewer 병렬화**
  - acceptance plateau + verify phase 한계가 확인된 경우에만.
  - Ellipsis 패턴 `[market-informed]`.
  - 초기 구성 예: (a) rule-based(현 엔진), (b) security-focused LLM,
    (c) performance-focused LLM. 결과는 filter pipeline에서 dedupe.
  - **폐기가 아닌 조건부 defer**. Phase A/B 이후 비용-효과 실측으로 재평가.

## 10. 업계 비교에 대한 운영 원칙

- 외부 벤더 수치는 **방향성 참고치**로만 쓴다.
- 내부 KPI 목표는 **반드시 내부 baseline 측정 후** 정한다.
- 본문에 vendor 수치 인용 시 반드시 `[market-informed]` 태그.
- few-shot 예시를 프롬프트에 직접 넣는 접근은 기본 금지
  (Greptile 실패 사례 `[market-informed]`).
  필요하면 filter pipeline / learned rule 쪽으로 간다.

## 11. 상세 설계 스케치

### 11.1 Verify Phase 흐름

```
Detect → FindingDecision(state=eligible, confidence=c)
         │
         ▼
   if c < VERIFY_THRESHOLD:
         │
         ▼
   LLM_self_check(prompt=[finding, evidence, change_snippet])
         │
         ▼
   {is_real_bug: bool, reasons: [str], new_confidence: float}
         │
   is_real_bug == False → state=suppressed, reason="verify:llm_self_check"
   new_confidence < minimum → state=suppressed, reason="verify:low_confidence"
```

- `review_runner.py`의 `_build_decision` 이후에 `_verify_if_uncertain(decision, evidence)` 훅 추가.
- 프롬프트는 엔진 response의 `reviewability`, `false_positive_risk`와 결합.

### 11.2 Acceptance Tracking

- `ThreadSyncState.resolution_reason`에 아래 값을 추가:
  - `fixed_in_followup_commit` — thread가 resolved로 transition되는 순간 이후 commit이
    `file_path:line_no ± 3 lines` 범위를 touch한 경우.
  - `remote_resolved_manual_only` — 사용자가 resolve 버튼만 눌렀고 range 변화가 없을 때.
- acceptance_rate = `fixed_in_followup_commit / (published + resolved)`.
- 참고: Bugbot의 resolution rate 개념 `[market-informed]`.

### 11.3 `.review-bot.yaml` 스키마 (초안, 설정 수렴 목적)

```yaml
version: 1

review:
  minimum_publish_score: 0.65
  severity_thresholds:
    critical: 0.9
    warning: 0.75
    suggestion: 0.6
    nitpick: 0.4
  collapsed_severities: [nitpick, suggestion]
  allowed_rules: [ALTI-MEM-007]
  suppressed_rules: [ALTI-STYLE-012]

paths:
  - glob: "tests/**"
    score_adjustment: -0.2
    suppress_rules: [ALTI-PERF-001]
  - glob: "src/security/**"
    minimum_score: 0.8
    promote_rules: [ALTI-SEC-*]

instructions: |
  이 repo는 Altibase storage engine 코어다.
  - 메모리 소유권과 예외 안전이 최우선.
  - 테스트 코드의 스타일 지적은 피한다.
  - suggestion 블록은 반드시 컴파일 가능해야 한다.

chat:
  ask_enabled: true
  ask_history_turns: 3
```

- `policy.json`과 충돌 시 우선순위는 `.review-bot.yaml` > `policy.json` > env.
- chat / autofix / advanced retrieval knob은 스키마 안정화 후 추가.

### 11.4 Walkthrough 노트 포맷 (초안)

```markdown
## 🤖 리뷰 봇 — MR 요약

**요지**: ownership API에 malloc→realloc 전환 2건, 테스트 3개 추가.

### 영향
- 수정된 symbol: `owner_alloc`, `owner_release` (호출 사이트 7곳)
- 호출부는 `src/storage/ownership/*.cpp`에 집중

### 주의해서 봐 주세요
- 🔴 `src/storage/ownership/ref.cpp:128` — realloc 실패 경로에서 원래 포인터 leak 가능
- 🟠 `src/storage/ownership/ref.cpp:214` — free() 직후 포인터 재사용 의심

> 전체 backlog는 `@review-bot backlog`로 확인할 수 있습니다.
```

- run summary와는 purpose를 분리해 `upsert_general_note(purpose="walkthrough")`로 게시.

## 12. 결론

- **현재 구조는 유지 가치가 높다.** 원본/Enhanced/Meta-eval 모두 동일한 결론.
- **가장 큰 기술 부채는 "검증 phase 부재"와 "트리거/측정 전제 미정리"**다.
- **context 강화는 필요하지만, verify + measurement보다 앞서지 않는다**.
- **walkthrough / ask / apply 같은 UX 기능은 신뢰도 기반이 깔린 뒤 붙인다**.
- **외부 제품 비교는 계속 참고하되, 내부 기준은 반드시 내부 데이터로 정한다**.

한 줄 요약:

> `review-bot`의 다음 단계는 "더 많이 지적하는 봇"이 아니라
> "더 믿을 수 있고, 더 맥락을 알고, 더 실행 가능한 제안을 하는 봇"이어야 한다.

## 부록 A. 현재 코드 참조점

- 파이프라인 엔트리: `review-bot/review_bot/worker.py`
- Detect/publish/sync 로직: `review-bot/review_bot/bot/review_runner.py`
- Command parser: `review-bot/review_bot/api/main.py` (`_extract_gitlab_note_command`)
- GitLab adapter: `review-bot/review_bot/review_systems/gitlab.py`
- Policy: `review-bot/review_bot/policy.py`
- Analytics: `review-bot/review_bot/api/main.py` (`/internal/analytics/rule-effectiveness`)
- Rule weight 학습: `review-bot/review_bot/bot/review_runner.py` (`_load_rule_effectiveness_weights`)
- Test DB isolation: `review-bot/tests/conftest.py`
- 트리거 무시 지점: `review-bot/review_bot/api/main.py:191-197`
- Run summary: `review-bot/review_bot/bot/review_runner.py:2303` (`_post_pr_summary`)
- Backlog helper: `review-bot/review_bot/bot/review_runner.py::_current_backlog_entries`
- Field 정의: `review-bot/review_bot/db/models.py` (`ThreadSyncState.resolution_reason`)

## 부록 B. 참고 자료 — `[market-informed]`

> 아래 수치는 모두 vendor self-report 또는 2차 정리글 기반. 내부 KPI 목표의 직접 근거가 아니다.

- CodeRabbit – product & docs: <https://www.coderabbit.ai/>, <https://docs.coderabbit.ai>
- CodeRabbit – large codebase: <https://www.coderabbit.ai/blog/how-coderabbit-delivers-accurate-ai-code-reviews-on-massive-codebases>
- Greptile – product & docs: <https://www.greptile.com>, <https://www.greptile.com/docs/introduction>
- Greptile – embedding 기반 코멘트 품질 개선 사례: <https://www.zenml.io/llmops-database/improving-ai-code-review-bot-comment-quality-through-vector-embeddings>
- Graphite Diamond: <https://diamond.graphite.dev/>
- Graphite – false positive 기대치: <https://graphite.com/guides/ai-code-review-false-positives>
- Graphite – Diamond eval 구축: <https://www.braintrust.dev/blog/graphite>
- Cursor Bugbot: <https://cursor.com/bugbot>
- Bugbot learned rules: <https://cursor.com/blog/bugbot-learning>
- Bugbot autofix: <https://cursor.com/blog/bugbot-autofix>
- Ellipsis 아키텍처: <https://www.zenml.io/llmops-database/building-and-deploying-production-llm-code-review-agents-architecture-and-best-practices>
- Ellipsis how-we-built: <https://www.ellipsis.dev/blog/how-we-built-ellipsis>
- Qodo Merge / PR-Agent: <https://github.com/qodo-ai/pr-agent>, <https://qodo-merge-docs.qodo.ai/>
- Qodo auto best practices: <https://qodo-merge-docs.qodo.ai/core-abilities/auto_best_practices/>
- Sourcery: <https://www.sourcery.ai/>, <https://docs.sourcery.ai/Code-Review/Overview/>
- GitHub Copilot code review: <https://docs.github.com/en/copilot/concepts/agents/code-review>
- 노이즈/신호 프레임워크: <https://dev.to/jet_xu/drowning-in-ai-code-review-noise-a-framework-to-measure-signal-vs-noise-304e>
- Cloudflare – AI 코드 리뷰 오케스트레이션: <https://blog.cloudflare.com/ai-code-review/>
- CodeRabbit – AI 코드 리뷰 툴 평가 프레임워크: <https://www.coderabbit.ai/blog/framework-for-evaluating-ai-code-review-tools>
- RAG/코드 그래프 조사: <https://arxiv.org/html/2510.04905v1>, <https://www.buildmvpfast.com/blog/repository-intelligence-ai-coding-codebase-understanding-2026>
