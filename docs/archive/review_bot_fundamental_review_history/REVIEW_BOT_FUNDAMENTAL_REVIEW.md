# 리뷰 봇 근원 점검 및 개선 방향 보고서

- 문서 상태: Draft for discussion
- 작성일: 2026-04-21
- 작성 목적: 현재 `review-bot`의 구조를 업계 reference와 비교하고,
  "이 방향이 맞는가" / "더 나은 방법은 없는가"에 실행 가능한 답을 낸다.
- 대상 독자: 리뷰 봇 구현 담당자, 설계 의사결정자, AI agent

---

## 0. Executive Summary

현재 `review-bot`은 "lifecycle-aware inline review bot"의 **기본 골격은 잘 잡혀 있다.**
`detect -> publish -> sync` 파이프라인, fingerprint 기반 dedupe, thread state 동기화, feedback 수용,
명시적 command 파서, current-state backlog view까지 — 업계 표준에 근접한 운영 구조를 갖췄다.

반면 2025–2026년 업계 최상위권 봇(CodeRabbit, Greptile, Diamond, Cursor Bugbot, Ellipsis, Qodo Merge)과 비교하면
아래 네 축에서 유의미한 gap이 있다.

| 축 | 현재 | 업계 top | Gap 요약 |
| --- | --- | --- | --- |
| **Context retrieval** | top-k RAG + file_context 4000자 | code graph, multi-hop, tool use | 단일 파일 이상 context가 약함 |
| **Noise 관리** | 정적 policy + 스코어 + feedback | self-verification, multi-pass, 대역별 agent | 검증 phase가 없음 |
| **Learning loop** | rule-level 가중치 (fingerprint 기반) | per-repo learned rules + embedding 유사도 기반 | 학습 granularity 및 개인화가 약함 |
| **Output UX** | inline + summary + full-report + backlog | walkthrough, sequence diagram, chat, auto-fix, one-click commit | 수용 가능한 제안 비율이 낮을 수 있음 |

결론: **이대로 가도 크게 틀리지 않지만**, 가장 가치 큰 다음 투자처는 "엔진을 더 복잡하게"가 아니라
(1) **검증 phase 도입** (2) **context graph 확장** (3) **제안의 actionability 강화** 세 축이다.

---

## 1. 현재 리뷰 봇 지형

### 1.1 파이프라인 한눈에 보기

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
     │  - remote_resolved / no_longer_eligible / anchor_changed
     │  - feedback 커맨드 ingest (bot:ignore / false-positive / later / allow)
     ▼
[ PR 일반 노트 ] summary + (optional) full-report / backlog / help
```

(세부: `review-bot/review_bot/bot/review_runner.py`, `review_bot/api/main.py`, `review_systems/gitlab.py`)

### 1.2 현재 강점

- **Inline-first.** canonical UI는 외부 리뷰 시스템(GitLab MR). 일반 노트는 보조 인터페이스.
- **Lifecycle 분리.** detect / publish / sync가 별도 queue로 분리되어 하나의 실패가 전체를 막지 않는다.
- **Thread sync 상태 모델이 명확.** `ThreadSyncState`가 open / resolved / stale / remote_reopened을 추적.
- **Feedback-aware.** `bot:ignore`, `bot:false-positive`, `bot:later`, `bot:allow`가 인라인 reply 수준에서 해석됨.
- **Dedupe 모델이 2단계.** fingerprint(동일 finding) + human_key(동일 사용자 지각) + anchor_signature(thread identity).
- **Policy hook.** path별 score_adjustment, minimum_score, suppress/promote 규칙 지원 (`policy.py`).
- **Rule learning 시그널이 존재.** 인간 resolve 비율로 rule 가중치 계산 (`_load_rule_effectiveness_weights`, fingerprint 기준).
- **보수적 command parser.** 최근 개편으로 불명확한 mention은 실행하지 않음.

### 1.3 관찰된 한계 (코드 기반 관찰)

1. **Context는 대부분 단일 파일.** `file_context`는 해당 파일의 앞 4000자만 주입. 호출 그래프/호출부/구조체 정의가 다른 파일에 있을 때 놓침.
2. **검증 단계가 없다.** 엔진+LLM 제안이 그대로 게시된다. 업계 최신은 "별도 agent가 의심점을 재검증"을 표준으로 삼는 추세.
3. **Learning granularity가 rule 단위에 고정.** 특정 파일/패턴에 대한 개인화나 per-repo learned rule 개념 없음.
4. **Auto-fix 루프가 없다.** `auto_fix_lines` 필드는 있으나 agent가 commit/branch하는 루프는 미구현.
5. **Walkthrough/요약이 제한적.** PR 수준 change summary, sequence diagram, "왜 이 MR이 중요한가" 같은 설명 산출물 없음.
6. **Chat이 없다.** `@review-bot ask ...` 같은 자연어 질의 경로 없음. 질문은 사람이 직접 쳐야 함.
7. **Rate limit은 프로세스 로컬.** 다중 인스턴스에서 각자 100 req/min을 허용하므로 실제 보호 효과 제한적 (`main.py:34`).
8. **Severity 분류가 score-threshold 선형 매핑.** 업계는 nitpick / suggestion / warning / critical을 별도 정책으로 분리하는 추세.
9. **테스트가 공유 SQLite.** 병렬 CI에 취약 (설계문서에서도 지적).
10. **리뷰 대상 언어/규칙이 C++ 및 내부 규칙셋 중심.** 확장 포인트는 열려 있지만 다국어 top-tier 수준은 아님.

---

## 2. 업계 Reference 봇 비교

### 2.1 조사 대상

| 봇 | 특징 요약 |
| --- | --- |
| CodeRabbit | massive codebase 지원, walkthrough + sequence diagram, 학습(Learnings), `.coderabbit.yaml` |
| Greptile | code graph 기반 multi-hop 조사, 82% catch rate 자체 보고, vector embedding으로 코멘트 품질 개선 |
| Graphite Diamond | 저 false-positive (sub-3% 자체 주장), 자체 PR 데이터로 eval set 구축, 수락률 KPI |
| Cursor Bugbot | multi-pass agentic verification, learned rules(44k+), 자체 검증 + autofix |
| Ellipsis | 병렬 comment generator + multi-stage filtering pipeline, thumbs 임베딩 유사도로 학습 |
| Qodo Merge (ex PR-Agent) | 오픈소스, 풍부한 slash command (`/review`, `/describe`, `/improve`, `/ask`), auto best practices |
| Sourcery | 다중 AI reviewer + 정적 분석 병행, `.sourcery.yaml`로 custom rule |
| GitHub Copilot Review | repo-wide `.github/copilot-instructions.md`, agentic tool calling, Enterprise 수준 |
| Sonar / DeepSource / Codacy | 전통 정적 분석, quality gate 중심 (AI는 부가) |

### 2.2 핵심 특성 비교 표

| 항목 | 현재 `review-bot` | CodeRabbit | Greptile | Diamond | Bugbot | Qodo | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| inline comments | O | O | O | O | O | O | 기본 |
| PR walkthrough/요약 | 요약 노트만 | O (diagram 포함) | O | O | O | `/describe` | **gap** |
| sequence diagram | X | O | - | - | - | - | 차별 포인트 |
| 자연어 chat (`ask`) | X | O | O | - | - | `/ask` | **gap** |
| multi-pass 검증 | X | O (일부) | O | O | O (핵심) | - | **gap** |
| codebase graph | X | O (codegraph) | O (코어 차별점) | O | - | - | **gap** |
| per-repo learned rules | rule-level 가중치 | Learnings | vector embedding | eval dataset 기반 | learned rules (핵심) | auto best practices | **gap** |
| slash/mention command | O (review/full-report/backlog/help) | O | O | O | O | 풍부 (`/improve` 등) | 부족 |
| false-positive 지표 | (구현 중) | - | 개선 공개 | sub-3% 주장 | 80% resolution rate | - | **측정 부재** |
| autofix(commit) | 필드만 있음 | O (pro) | - | - | O | - | **gap** |
| multi-repo / cross-repo | X | O (Multi-Repo Analysis) | O | - | - | - | **gap (장기)** |
| config file | env vars + policy.json | `.coderabbit.yaml` | UI | UI | UI | `.pr_agent.toml` | **gap (UX)** |
| 내부 규칙 엔진 | O (`review-engine`) | 부분 | - | - | - | - | 강점 |

### 2.3 업계에서 수렴하고 있는 공통 패턴

1. **"flag → verify → post" 3단 구조.** Bugbot은 multi-pass, Ellipsis는 multi-stage filter, CodeRabbit은 shell/Python 실행으로 증거 수집. 공통 메시지: *모델을 믿지 말고 증거를 요구하라.*
2. **Learned rules / knowledge base.** feedback을 그대로 프롬프트에 넣는 대신, 유사 코멘트 embedding이나 rule로 규범화한다. few-shot을 프롬프트에 직접 넣는 접근은 Greptile 실험 결과 오히려 악화됐다.
3. **severity는 정책으로 다룬다.** critical/warning/suggestion/nitpick 같은 층위를 분리하고, `suggestion` 이하는 "tap to expand"처럼 접어 노이즈를 줄인다.
4. **Walkthrough가 별도 산출물.** 라인 단위 코멘트와 별개로 "이 MR은 무엇을 바꾸는가"를 요약하는 노트 또는 diagram을 낸다. 리뷰어가 PR을 열자마자 30초 안에 파악할 수 있게 한다.
5. **수락률(acceptance rate)을 1급 KPI로 쓴다.** Diamond은 "내부 PR에서 수락된 코멘트 비율"을 운영 KPI로 박았다. comment count가 아니라 **실제 반영된 비율**이 지표.
6. **auto-fix는 검증된 경우에만.** Bugbot은 fix 후 build verification을 실행. CodeRabbit autofix는 merge를 대신하지 않음. "AI가 코드를 쓰게 하되 merge 결정은 사람"이라는 경계선은 공통.
7. **설정은 repo 안에 yaml로.** `.coderabbit.yaml`, `.sourcery.yaml`, `.github/copilot-instructions.md`, `.pr_agent.toml` — 설정이 repo에 들어간다. 리뷰 봇은 PR 맥락을 알 수 있고 review 결정이 reproducible해진다.

---

## 3. Gap 분석

현재 시스템 대비 의미 있는 gap을 **우선순위 순으로** 정리한다.

### 3.1 신뢰도 (Must-fix)

**3.1.1 수락률 / signal 비율이 측정되지 않는다.**

- 현재: `/internal/analytics/rule-effectiveness`가 resolve_rate / human_resolve_rate를 반환.
- 한계: "이 코멘트가 실제로 코드 수정을 유발했는가"는 미측정. GitLab `resolved` 만으로는 resolve 이유가 "고쳤다"인지 "무시했다"인지 구분이 약함.
- 업계: Bugbot은 **AI judge가 "flag된 이슈가 실제로 merged diff에서 바뀌었는가"**를 계산 (resolution rate).
- 제안: `resolved_reason` 추가 (`fixed_in_followup_commit` / `dismissed_by_user` / `no_longer_relevant`). ThreadSyncState에 컬럼 추가 + sync phase에서 이후 commit 추적.

**3.1.2 검증 phase가 없다.**

- 현재: 엔진 제안 → 점수 필터 → 게시.
- 업계 공통: 엔진 제안 → **별도 agent가 증거 재검증** → 실패 시 drop.
- 제안: `verify` phase를 `detect` 이후 선택적으로 삽입. 두 가지 모드를 지원.
  - (a) **rule-execution 검증**: finding이 "free() 후 NULL 미대입"처럼 패턴 기반이면, 엔진이 돌려준 line에서 실제로 그 패턴이 성립하는지 regex/AST로 재확인.
  - (b) **LLM self-check**: "이 finding이 false positive일 가능성이 높은 이유 3가지를 제시하라"를 추가 LLM 호출로 돌리고, 확신도가 임계값 이하이면 drop.

**3.1.3 Severity가 score 함수의 종속 변수다.**

- 현재: `_severity_from_score(score) → low/medium/high`. score가 severity를 결정.
- 문제: "아주 확신하는 nitpick"과 "애매한 critical"이 같은 점수대로 눌릴 수 있다.
- 제안: severity는 rule/finding이 자기주장하게 하고, score는 publish 여부만 결정. `nitpick` / `suggestion` / `warning` / `critical` 네 층위를 분리. `suggestion` 이하는 collapsed note로만 게시.

### 3.2 Context / Retrieval (High)

**3.2.1 context가 현재 파일에 갇혀 있다.**

- 현재: `file_context`는 대상 파일의 첫 4000자만 포함. 호출부, 구현부, 관련 include 파일은 반영되지 않음.
- Greptile/Diamond의 차별점: **code graph 기반 multi-hop**.
- 제안 (점진적):
  1. 엔진 쪽에 이미 vector DB가 있다면, 같은 diff에서 수집된 symbol 기준으로 top-k "related file" excerpt를 추가 주입.
  2. `ctags` / LSP index로 정의/참조 1-hop을 돌려 호출 사이트 excerpt를 포함.
  3. 중기: "finding-level RAG"를 별도로 둔다. 현재 retrieval은 diff 기반이지만, 각 finding은 자체 context를 가진 mini-query로 한 번 더 검색하는 편이 정확도가 높다.

**3.2.2 diff 분할이 lexical.**

- 현재: 80줄 hunk로 자른다. 함수/블록 경계를 안 본다. 결과적으로 "이 블록의 의미"를 LLM이 재구축해야 함.
- 제안: tree-sitter로 function / method 경계를 뽑아 "함수 단위 review unit"로 split. 해당 함수 body 전체를 review_unit.patch로 쓰면 file_context 없이도 근접 context가 확보됨.

### 3.3 Learning (High)

**3.3.1 학습 단위가 rule 전체.**

- 현재: `_load_rule_effectiveness_weights`는 rule_no 단위 global 가중치. 같은 rule이라도 "이 repo에서는 유용하지만 저 repo에서는 거의 false-positive"인 경우를 반영 못 함.
- 업계: Cursor Bugbot은 "이 repo의 이 rule은 reply로 '이건 의도된 동작이다'가 반복 → learned rule로 suppress" 구조.
- 제안:
  - rule 가중치를 `(project_ref, rule_no)` 단위로 확장. 기존 함수를 `_load_rule_effectiveness_weights(*, scope)` 로 확장하고 default는 project 범위.
  - 인간 reply embedding → 유사 과거 코멘트가 '무시'로 끝난 비율을 계산, 이를 scoring에 반영 (Ellipsis 패턴). 초기엔 제목+요약의 단순 문자열 유사도(`difflib`)로도 유효 신호가 잡힌다.

**3.3.2 sampling 편향.**

- 현재: "5건 이상"이 rule weight 학습의 최소. 적은 트래픽 rule은 영원히 중립 유지.
- 대안: Bayesian smoothing. rule 전체 prior를 계산하고, rule별 관측치를 prior와 혼합. 5건 임계값 없이도 가중치가 의미를 가짐.

### 3.4 Output UX / Actionability (High)

**3.4.1 PR walkthrough 부재.**

- 현재: 요약 노트는 "이 run에서 게시된 finding 개수"를 위주로 보여줌.
- 제안: `@review-bot summarize` (또는 MR 오픈 시 자동) → 아래 3항목을 일반 노트 하나로 게시.
  1. **변경 요약** (LLM에게 diff + 파일 목록을 주고 2–4줄)
  2. **영향 범위** (수정된 symbol/함수 리스트 + 해당 symbol의 호출 사이트 수)
  3. **주의 포인트** (이 run에서 게시된 critical/warning finding 요약 + 수가 많다면 top-3만)
- 이 노트는 `upsert_general_note(purpose="walkthrough")`로 append-only가 아니게.

**3.4.2 제안이 "읽을 것"에 그친다.**

- 현재: `suggested_fix` 텍스트 + 신뢰도 높은 경우 ```suggestion``` 블록. GitLab의 "Apply suggestion" 버튼은 쓸 수 있으나 일반화되어 있지 않음.
- 제안 (단계적):
  1. suggestion block이 확실하게 컴파일되는 경우에만 노출. "확신도 >= 0.9 && 교체 라인 수 ≤ 5" 같은 보수 기준.
  2. 중기: autofix 플로우. `@review-bot apply <thread-ref>` 커맨드 → 별도 branch 생성 → suggestion을 패치로 적용 → draft MR/커밋 push. merge는 여전히 사람이.
  3. **검증된 fix만 commit.** fix 적용 후 기본 빌드 or lint을 돌리고 실패 시 rollback.

**3.4.3 Chat / `ask` 부재.**

- 현재: 사용자는 리뷰 봇에게 "이게 왜 false positive인가?"를 자연어로 물을 수 없다. `bot:false-positive` 같은 command만 가능.
- 제안: `@review-bot ask <질문>`을 추가. thread context + diff + 관련 파일 excerpt를 모아 LLM에 위임, 답변을 thread reply로 게시. 동일 thread 안에서는 대화가 이어지도록 history를 3턴 유지.

### 3.5 운영 / 신뢰성 (Medium)

**3.5.1 Rate limit이 process-local.**

- 이미 문서에도 언급 (`main.py:32-35`). 다중 인스턴스 배포 시 초과 risk.
- 제안: Redis 기반 sliding window로 교체. 쓰이는 Redis 인프라가 이미 있으므로 비용 낮음.

**3.5.2 SQLite 기반 테스트 fixture 공유.**

- 설계 문서에서도 지적. 병렬 CI에 취약.
- 제안: pytest fixture마다 `BOT_DATABASE_URL` 주입, 파일별 독립 DB 파일. xdist 지원은 선언만 하고 공식화.

**3.5.3 설정이 env var 중심.**

- 업계는 repo 안 yaml이 표준. `review-bot`은 `policy.json`이 그 역할을 일부 맡지만 chat instruction / walkthrough 스타일 / suppression set은 환경변수 + DB 쪽에 분산.
- 제안: `.review-bot.yaml`을 repo root에서 읽어 다음을 통합 표현.
  - `review.minimum_publish_score`
  - `review.severity_thresholds`
  - `review.suppressed_rules` / `allowed_rules`
  - `paths[...]` (현재 `policy.json`과 유사)
  - `instructions` (CodeRabbit/Copilot과 유사한 자유 서술)
- `policy.json`은 남겨두되 `.review-bot.yaml`이 우선.

### 3.6 Observability (Medium)

**3.6.1 supplied metric이 limited.**

- 현재: `/metrics`로 Prometheus 지표 있음 (queue depth, duration 등).
- 제안 메트릭:
  - `review_comments_posted_total{severity,rule_no}` (이미 가까운 것 있음)
  - `review_comments_resolved_total{resolution_reason,rule_no}`
  - `review_comments_acceptance_rate{window="7d",project}` — fix-commit 유발 비율
  - `review_feedback_commands_total{command}` — ignore/false-positive/later/allow 빈도
  - `verify_phase_drop_total{reason}` (검증 단계 도입 시)

### 3.7 장기 (Defer)

- **Cross-repo analysis.** CodeRabbit이 3월에 출시한 기능. Altibase처럼 단일 repo가 크면 가치 낮음. 우선순위 낮음.
- **Multi-lang 확장.** 현재 C++ 가정이 박혀 있음 (`CPP_EXTENSIONS`). 시기가 올 때까지 defer.
- **IDE 통합.** Sourcery처럼 editor에서 실시간 리뷰는 별개 product 영역. 현 단계에선 scope out.

---

## 4. "이 방향이 맞는가?" — 판단

### 4.1 유지할 결정 (올바른 방향)

- **Inline-first / lifecycle-aware.** 업계 표준과 정렬.
- **fingerprint + anchor_signature 이중 dedupe.** 수렴하는 설계. 유지.
- **feedback 커맨드를 thread reply에서 해석.** 업계 비교해도 뒤처지지 않음. Sourcery/CodeRabbit도 유사.
- **current-state backlog view.** 최근 개편 방향(`ThreadSyncState` 기반 backlog)은 정확히 맞음.
- **policy 기반 path override + suppress/allow.** 업계와 같은 방향.
- **queue 기반 detect/publish/sync 분리.** 실패 국소화에 유리.

### 4.2 재검토할 결정

1. **Severity = f(score) 매핑.** 위 3.1.3.
2. **Rule 가중치가 global.** 위 3.3.1.
3. **검증 phase 미도입.** 위 3.1.2. 가장 큰 기술적 부채.
4. **Context가 단일 파일.** 위 3.2.1.
5. **리뷰 봇 설정이 environment + policy.json으로 분산.** 위 3.5.3.

### 4.3 대안을 적극 고려할 지점

- **엔진을 "retrieval + ranking"으로 재정의, review 로직은 LLM provider 쪽으로.** 현재 엔진은 rule_no 레벨의 탐지 결과를 돌려주지만, 실제 comment 텍스트 생성은 provider가 한다. 이 경계선은 지금대로 유지해도 되지만, 엔진이 "fingerprint 후보 + 구조화된 증거"를 반환하고, review provider가 "어떤 걸 게시할지 + 어떻게 말할지"를 전담하는 쪽이 *검증 단계 삽입에 유리*.
- **`bot:` 커맨드를 policy-as-data로 접근.** `bot:ignore`가 반복되면 learned rule에 남겨, 다음 동일 프로젝트 run에서 자동 suppress. 현재는 ThreadSyncState 기반 + 그때그때 해석.

---

## 5. 개선 로드맵

우선순위는 **신뢰 → context → 학습 → 자동화** 순.

### Phase A (0–2주): 신뢰 기반 (Must-fix)

A1. **Acceptance metric 추가** — `ThreadSyncState.resolution_reason`에 `fixed_in_followup_commit` 케이스 분류. sync phase에서 이후 commit diff가 해당 finding 라인을 touch했는지 판정. 기존 `remote_resolved`만 쓰는 해석을 세분화.

A2. **severity/score 분리** — `FindingDecision.severity`는 provider/엔진이 정한 값을 그대로 보존하고, `_severity_from_score`는 *fallback only*. 기본 severity `nitpick`은 "접힘 모드"로만 게시 (`<details>` 블록).

A3. **LLM self-check 옵션 도입** — 설정 `BOT_VERIFY_WITH_LLM_CONFIDENCE=0.85`. `_build_decision` 직후, 확신도 임계값 이하 finding에 대해 추가 LLM 호출로 "false positive일 이유"를 뽑아 확신도를 재평가. 드롭 이유는 `verify:llm_self_check`.

A4. **Distributed rate limit** — `main.py`의 per-IP deque를 Redis-backed sliding window로 교체.

A5. **KPI 지표** — `review_comments_acceptance_rate` / `verify_phase_drop_total` Prometheus 메트릭 추가.

### Phase B (2–6주): Context 강화 (High)

B1. **Function-level review unit split** — `_iter_review_units`를 tree-sitter 기반으로 교체. C++에 한해서 먼저 도입 (existing `CPP_EXTENSIONS`). hunk가 함수 하나보다 작으면 function body 전체를 review_unit.patch로, 크면 기존 80 라인 split.

B2. **Symbol 기반 관련 파일 retrieval** — diff에서 touched symbol을 ctags/LSP로 추출 → 각 symbol의 정의 파일 상위 N개 excerpt를 engine 호출 payload `file_context`에 병합 주입.

B3. **Finding-level second retrieval (optional)** — 각 finding의 title+summary로 `search_codebase`를 재호출해 유사 과거 finding을 2–3개 포함. "비슷한 건은 최근 X MR에서 accept/ignore"의 힌트를 프롬프트에 추가.

B4. **`.review-bot.yaml` 통합 설정** — repo root에서 읽어 `policy.json` + env 일부를 대체. 리뷰 봇 부팅 시 warn-only 검증 후 적용.

### Phase C (6–10주): Learning 루프

C1. **(project_ref, rule_no) 단위 가중치** — `_load_rule_effectiveness_weights(scope=(project, rule_no))`. cache 무효화는 project 단위.

C2. **Embedding 유사도 기반 suppression** — 새 finding의 (title+summary+file_path) embedding을 계산, 과거 `bot:ignore`/`bot:false-positive` feedback을 받은 finding의 embedding과 cosine 유사도 0.9 이상이면 pre-publish에서 `suppressed(reason=learned:similar_ignore)` 처리. vector store는 작게 시작(프로젝트당 N천 건 수준이면 in-process FAISS 충분).

C3. **Walkthrough 노트** — `@review-bot summarize` (또는 MR 오픈 webhook에서 옵션 트리거). 3문단 요약 + 영향 symbol + 주목 finding top 3.

C4. **`@review-bot ask <질문>`** — thread context + diff를 LLM에 위임. thread reply로 게시. 동일 thread 히스토리 3턴 유지.

### Phase D (10주+): 자동화 확장

D1. **Autofix 플로우** — 확신도 ≥ 0.9 + suggestion block 존재 finding에 한해 `@review-bot apply` 지원. branch 생성 → patch → CI gate 통과 시 MR 코멘트로 "fix branch pushed: fix/bot-xxxx" 게시. merge는 사람이.

D2. **Nitpick 접힘 모드** — GitLab `<details>` 블록으로 `suggestion/nitpick`은 기본 collapsed.

D3. **Multi-reviewer parallel agent** — Ellipsis-like 병렬 generator. 초기엔 (a) rule-based (현 엔진), (b) security-focused LLM, (c) performance-focused LLM 3개 정도. 결과 합치고 filter phase에서 dedupe.

---

## 6. 각 개선 사항 상세 설계 스케치

### 6.1 Verify Phase

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

- `review_runner.py`의 `_build_decision` 이후 훅 `_verify_if_uncertain(decision, evidence)` 추가.
- 프롬프트는 엔진 response의 `reviewability`, `false_positive_risk`와 결합.

### 6.2 Acceptance Tracking

ThreadSyncState의 `resolution_reason`에 `fixed_in_followup_commit` 추가:

- sync phase에서 thread가 `resolved` 상태로 transition되는 순간, finding의 `file_path:line_no` 주변 ±3라인을 최근 commit diff로 조회.
- 해당 범위가 실제로 바뀌었으면 `resolution_reason=fixed_in_followup_commit`.
- 그렇지 않고 사용자가 직접 resolve 버튼을 눌렀을 뿐이면 `remote_resolved_manual_only`.
- 메트릭 `review_comments_acceptance_rate`는 `fixed_in_followup_commit / (published + resolved)`.

이건 Bugbot의 resolution rate 계산 방식을 차용한 것이다.

### 6.3 `.review-bot.yaml` 예시

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

### 6.4 Walkthrough 노트 포맷 (초안)

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

---

## 7. Metric 가이드 (신뢰도 판단용)

| 이름 | 정의 | 목표 |
| --- | --- | --- |
| **acceptance_rate** | `fixed_in_followup_commit / (published + resolved)` | Phase A 후 > 40%, Phase B 후 > 55%, Phase C 후 > 65% |
| **signal_ratio** | non-nitpick published / total published | > 70% |
| **ignore_rate** | `bot:ignore` + `bot:false-positive` 누적 / published | < 15% |
| **verify_drop_rate** | verify phase에서 drop된 수 / verify 대상 수 | 20–40% 권장 (너무 적으면 verify 미발동, 너무 많으면 model 문제) |
| **walkthrough_coverage** | walkthrough 노트가 게시된 MR / 전체 MR | > 80% (optional 트리거 시) |

업계 bench:

- Diamond: 자체 주장 false positive < 3%.
- Bugbot: resolution rate 80% (2026-04 기준). 여기가 industry north star.
- Greptile: addressed comments 비율을 19% → 55%로 끌어올린 사례.

KPI를 먼저 설치하고 이후 개선 작업의 판단 기준으로 쓰는 편이 안전.

---

## 8. 결론

- **방향성은 맞다.** inline-first + lifecycle-aware + feedback-aware 구조는 업계 표준이며,
  최근 개편 (backlog을 current state에서 도출, fingerprint-단위 analytics, explicit command parser)은
  업계 top 봇이 가는 방향과 동일하다.
- **탐지 모델을 더 복잡하게 만드는 데 투자하지 말라.** 현 단계에서 가장 가치 큰 투자는
  (1) **verify phase 도입** (2) **context graph 확장** (3) **actionable output (walkthrough + autofix)** 순.
- **KPI 없이 개선을 시작하지 말라.** acceptance_rate부터 설치하고, Phase A 이후 모든 기능은
  이 메트릭 변화로 판정하는 방식을 권장.
- **`.review-bot.yaml`로 설정 표면을 수렴시키는 편이 장기적으로 이득.**
  운영 팀이 repo만 보고 리뷰 봇 동작을 예측할 수 있게 한다.
- **학습은 rule 단위에서 (project, rule) 단위로, 그 다음 embedding-유사도로.**
  Greptile의 few-shot 실험 실패 사례를 고려할 때, 프롬프트에 예시를 밀어 넣는 접근은 피하고
  filter pipeline / learned rule 쪽으로 간다.

다음 산출물 제안:

1. Phase A의 A1 (acceptance tracking) + A2 (severity 분리) 두 개만 먼저 설계문서로 격상.
2. `.review-bot.yaml` 스키마 초안을 설계 문서로 분리.
3. Phase A, B 완료 후 본 문서를 재평가.

---

## 부록 A. 현재 코드상의 주요 참조점

- 파이프라인 엔트리: `review-bot/review_bot/worker.py`
- Detect/publish/sync 로직: `review-bot/review_bot/bot/review_runner.py`
- Command parser: `review-bot/review_bot/api/main.py` (`_extract_gitlab_note_command`)
- GitLab adapter: `review-bot/review_bot/review_systems/gitlab.py`
- Policy: `review-bot/review_bot/policy.py`
- Analytics: `review-bot/review_bot/api/main.py` (`/internal/analytics/rule-effectiveness`)
- Rule weight 학습: `review-bot/review_bot/bot/review_runner.py` (`_load_rule_effectiveness_weights`)

## 부록 B. 참고 자료

- CodeRabbit – product & docs: <https://www.coderabbit.ai/>, <https://docs.coderabbit.ai>
- CodeRabbit – large codebase engineering: <https://www.coderabbit.ai/blog/how-coderabbit-delivers-accurate-ai-code-reviews-on-massive-codebases>
- Greptile – product & docs: <https://www.greptile.com>, <https://www.greptile.com/docs/introduction>
- Greptile – embedding 기반 코멘트 품질 개선 사례: <https://www.zenml.io/llmops-database/improving-ai-code-review-bot-comment-quality-through-vector-embeddings>
- Graphite Diamond: <https://diamond.graphite.dev/>
- Graphite – false positive 기대치: <https://graphite.com/guides/ai-code-review-false-positives>
- Graphite – Diamond 평가 셋 구축: <https://www.braintrust.dev/blog/graphite>
- Cursor Bugbot: <https://cursor.com/bugbot>
- Bugbot learned rules: <https://cursor.com/blog/bugbot-learning>
- Bugbot autofix: <https://cursor.com/blog/bugbot-autofix>
- Ellipsis 아키텍처: <https://www.zenml.io/llmops-database/building-and-deploying-production-llm-code-review-agents-architecture-and-best-practices>
- Ellipsis how-we-built: <https://www.ellipsis.dev/blog/how-we-built-ellipsis>
- Qodo Merge / PR-Agent: <https://github.com/qodo-ai/pr-agent>, <https://qodo-merge-docs.qodo.ai/>
- Qodo auto best practices: <https://qodo-merge-docs.qodo.ai/core-abilities/auto_best_practices/>
- Sourcery: <https://www.sourcery.ai/>, <https://docs.sourcery.ai/Code-Review/Overview/>
- GitHub Copilot code review: <https://docs.github.com/en/copilot/concepts/agents/code-review>
- 노이즈/신호 프레임워크 (실무자 글): <https://dev.to/jet_xu/drowning-in-ai-code-review-noise-a-framework-to-measure-signal-vs-noise-304e>
- Cloudflare – AI 코드 리뷰 오케스트레이션: <https://blog.cloudflare.com/ai-code-review/>
- AI 코드 리뷰 툴 평가 프레임워크 (CodeRabbit 블로그): <https://www.coderabbit.ai/blog/framework-for-evaluating-ai-code-review-tools>
- RAG/코드 그래프 최신 조사: <https://arxiv.org/html/2510.04905v1>, <https://www.buildmvpfast.com/blog/repository-intelligence-ai-coding-codebase-understanding-2026>
