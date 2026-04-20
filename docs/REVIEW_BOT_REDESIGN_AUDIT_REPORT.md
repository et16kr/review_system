# 리뷰 봇 근원 점검 및 재설계 판단 보고서

- 작성일: 2026-04-20
- 대상: `review-bot`, `review-engine`, GitLab 연동 경로, 운영 문서, 테스트 자산
- 관점: GitLab-first, 그러나 GitHub/Gerrit 등 다른 SCM에도 이식 가능한 설계 원칙 중심
- 외부 비교 기준: 2026-04-20 시점의 공식 문서만 사용

## 1. Executive Summary

본 시스템의 큰 방향은 완전히 잘못된 것이 아니다. `external Git UI -> review-bot -> review-engine` 분리는 유지할 가치가 있다. 외부 Git UI를 canonical review surface로 두고, 봇은 오케스트레이션과 게시를 담당하며, 엔진은 규칙 지식과 탐지에 집중하게 만드는 구조는 확장 가능한 출발점이다.

다만 현재 구현은 "운영형 리뷰 봇"이라기보다 "좋은 MVP의 말단"에 가깝다. 지금 가장 큰 문제는 모델 성능보다 계약과 lifecycle이다. 탐지 상류의 계약 테스트가 이미 하나 깨져 있고, adapter 계약이 실제 리뷰 운영에 필요한 thread 조회·갱신·해결·피드백 회수를 표현하지 못하며, DB identity도 `pr_id` 단일 정수에 기대고 있어 멀티 프로젝트/멀티 SCM 확장이 구조적으로 어렵다. 문서는 아직 summary-note MVP를 전제로 쓰여 있는데, 실제 GitLab adapter는 inline discussion을 시도하고 있어 문서와 런타임도 어긋난다.

결론은 다음과 같다.

- 매크로 방향은 유지해도 된다.
- 미시 구조는 재설계가 필요하다.
- 기본 권고안은 "현 구조 유지 + 하드닝"이 아니라 "하이브리드 재설계"다.
- 특히 LLM은 1차 탐지기보다 `explainer`와 `triage assistant` 역할로 내리는 편이 더 안전하다.

권고하는 목표 구조는 다음과 같다.

```text
detect -> validate -> score -> explain -> publish -> learn
```

여기서 핵심은 다음 네 가지다.

- 탐지는 규칙/패턴/정적 신호가 맡는다.
- 게시 여부 판단은 score/dedupe/policy 계층이 맡는다.
- LLM은 최종 코멘트 문구와 수정 가이드를 생성한다.
- publish 이후 thread 상태와 reviewer feedback을 다시 학습 루프로 회수한다.

즉, 현재 구조를 버리기보다, "봇/엔진 분리"는 유지하고 "계약·데이터모델·lifecycle"을 재설계하는 쪽이 가장 합리적이다.

## 2. 현재 아키텍처와 실제 동작 흐름

현재 저장소의 명시적 방향은 아래와 같다.

```text
External Git Review System ---> review-bot ---> review-engine
```

`docs/WORKSPACE_SPLIT_ARCHITECTURE.md`는 외부 Git 리뷰 시스템을 canonical UI로 두고, `review-bot`만 `review-engine`을 호출하며, 외부 시스템 연동을 adapter로 분리한다는 원칙을 명시한다.

실제 동작 흐름은 대략 아래와 같다.

1. GitLab webhook이 `review-bot` API로 들어온다.
2. `open/update/reopen`만 수용하고, `update`인데 `oldrev`가 없으면 새 커밋이 없는 업데이트로 간주해 무시한다.
3. `review_run`이 생성되고 RQ worker에 enqueue된다.
4. worker는 review request diff를 가져온다.
5. C/C++ 파일의 patch를 review unit으로 쪼개고, 각 unit을 `review-engine`에 `top_k=8`로 조회한다.
6. 상위 결과 중 `auto_review` 대상과 최소 score를 넘는 항목만 남긴다.
7. provider가 한국어 코멘트 초안을 만들고, changed-line anchor를 맞춘다.
8. dedupe와 batch selection을 거쳐 GitLab inline discussion으로 게시한다.

현재 구현에서 이미 괜찮은 설계 씨앗도 있다.

- GitLab이 large diff에서 patch를 생략할 때 raw file을 다시 읽어 patch를 재구성한다.
- 새 커밋이 없는 MR update webhook은 무시해 중복 리뷰를 줄인다.
- `manual_only`와 `reference_only`를 metadata로 갖고 있어 자동 게시 범위를 줄일 수 있다.
- inline anchor가 실패했을 때 무분별하게 general note로 fallback하지 않도록 막아 두었다.
- dedupe, diversity batching, changed-line 정확도 보정이 이미 구현되어 있다.

즉, 문제는 "아이디어가 없다"가 아니라 "좋은 조각들이 있는데 운영형 계약으로 아직 승격되지 못했다"에 가깝다.

## 3. 핵심 진단 결과

### 3.1 High Severity

#### H1. 정확도 체인의 상류 계약이 이미 깨져 있다

`review-engine` 테스트는 현재 `1 failed, 48 passed`이며, 실패한 테스트는 `ide_rc_flow` 패턴이 검출되지 않는 계약 위반이다. `review-engine/tests/test_altidev4_diff_contract.py`는 example diff에서 `ide_rc_flow`가 검출되어야 한다고 기대하지만, 실제 extractor는 `IDE_RC` 존재만으로는 패턴을 만들지 않고 별도의 flow signal regex까지 요구한다. 예제 diff `queue_perf_memory_and_rc.diff`에는 `IDE_RC sRet;`만 있고 flow signal이 충분하지 않다.

이 문제는 단순한 테스트 1건이 아니다. 탐지 상류 계약이 흔들리면 score, dedupe, prompt 개선, 코멘트 문구 개선으로는 복구할 수 없다. 리뷰 봇은 downstream cosmetics보다 upstream evidence integrity가 더 중요하다.

판단:

- 현재 retrieval/detector 계층은 "쓸 수 없다" 수준은 아니지만, "정확도 체인의 기준점"으로 쓰기에는 아직 불안정하다.
- 최소한 diff manifest와 pattern extractor 중 무엇이 정답인지 정리한 뒤 계약을 고쳐야 한다.

#### H2. `ReviewSystemAdapter` 계약이 실제 리뷰 lifecycle을 표현하지 못한다

`review-bot/app/review_systems/base.py`의 adapter 계약은 사실상 세 가지뿐이다.

- `get_pull_request_diff`
- `post_comment`
- `post_status`

그런데 실제 운영형 리뷰 봇에는 최소한 다음이 필요하다.

- review request metadata 조회
- 기존 thread 조회
- comment update/upsert
- thread resolve/unresolve
- head/base/start sha와 anchor validity 재검증
- reviewer feedback 회수
- status/check publishing

현재 GitLab adapter는 이미 inline discussion 생성까지 시도한다. 반면 문서(`docs/API_CONTRACTS.md`, `docs/OPERATIONS_RUNBOOK.md`)는 여전히 summary note 중심 MVP를 전제로 쓰고 있다. 즉, 구현이 문서보다 앞서 나갔는데, 정작 base contract는 그 수준까지 진화하지 못했다.

판단:

- 지금 구조에서 가장 큰 병목은 "모델"이 아니라 "adapter contract"다.
- 이 계약을 넓히지 않으면 thread-state sync, comment reconciliation, feedback learning을 붙일 수 없다.

#### H3. 현재 identity model은 멀티 프로젝트/멀티 SCM에 취약하다

DB 모델은 `ReviewRun.pr_id`, `ReviewFinding.pr_id`, `FindingPublication.pr_id` 중심으로 설계되어 있다. webhook도 GitLab MR `iid`를 그대로 `pr_id`로 넣는다. 동시에 GitLab adapter는 `GITLAB_PROJECT_ID` 단일 환경변수에 의존한다.

이 조합은 다음 문제를 만든다.

- 프로젝트 A의 MR `iid=34`와 프로젝트 B의 MR `iid=34`를 구분하기 어렵다.
- 같은 GitLab 인스턴스 내 멀티 프로젝트 확장이 자연스럽지 않다.
- GitHub/Gerrit 같은 다른 review system으로 일반화하기 어렵다.
- comment/thread/status를 외부 시스템의 canonical identity와 연결해 관리하기 힘들다.

판단:

- 현 스키마는 단일 프로젝트 PoC에는 충분하지만, 운영형 봇의 기본 키로는 부족하다.
- `review_system + project_ref + review_request_id` 복합 키로 승격해야 한다.

#### H4. workspace/package 경계가 흔들려 개발 경험과 테스트 신뢰성이 낮다

루트 `pyproject.toml`, `review-bot/pyproject.toml`, `review-engine/pyproject.toml`가 모두 `app` 패키지를 사용한다. 각 하위 프로젝트에서 자기 디렉터리 기준으로 테스트를 돌리면 돌아가지만, 루트 기준으로 `uv run --project review-bot --extra dev python -m pytest -q`를 실행하면 루트 `tests/conftest.py`와 루트 `app` import가 끼어들며 `chromadb` 누락으로 실패한다.

이 문제는 단순한 테스트 스크립트 불편이 아니다.

- import resolution이 실행 위치에 따라 달라진다.
- IDE, CI, 로컬 bootstrap에서 어떤 `app`이 잡히는지 예측성이 낮다.
- 서비스 분리 원칙이 패키지 경계에서 다시 섞인다.

판단:

- 현재 저장소는 "구조적으로 분리된 것처럼 보이지만 import path 관점에서는 아직 분리되지 않았다."
- 서비스별 top-level package rename 또는 monorepo workspace 규칙 정리가 필요하다.

#### H5. thread-state 부재로 인해 "리뷰 생성"은 되지만 "리뷰 운영"이 안 된다

현재 상태 모델은 대체로 `open/published/failed_publication` 수준이다. 게시 실패는 남기지만, 게시된 thread가 이후 push에서 해결되었는지, stale이 되었는지, reviewer가 무시했는지, 같은 finding을 update해야 하는지에 대한 sync 상태가 없다.

이는 실무에서 더 큰 문제를 만든다.

- 같은 이슈를 새 커밋마다 다시 올릴 위험이 있다.
- 이미 해결된 thread를 닫거나 stale 처리하기 어렵다.
- reviewer feedback을 다음 run의 suppression signal로 쓰기 어렵다.
- "봇이 코멘트를 남긴다"와 "봇이 팀의 리뷰 흐름에 참여한다" 사이의 차이를 메우지 못한다.

판단:

- 현재 봇은 publishing bot에 가깝고, review lifecycle bot으로는 아직 아니다.

### 3.2 Medium Severity

#### M1. 문서와 런타임이 어긋난다

`docs/API_CONTRACTS.md`와 `docs/OPERATIONS_RUNBOOK.md`는 GitLab adapter를 summary note 중심 MVP로 설명한다. 반면 코드에서는 inline discussion을 직접 생성한다. 이런 drift는 향후 운영 장애 때 더 크게 문제 된다.

영향:

- 운영자가 실제 동작을 잘못 이해할 수 있다.
- 장애 대응 시 fallback 정책을 오판할 수 있다.
- 이후 구현자가 이미 끝난 것과 아직 안 된 것을 구분하기 어렵다.

#### M2. migration, retry/backoff, structured observability가 얇다

DB 초기화는 `Base.metadata.create_all()`에 머물고 있고, worker는 단순 RQ loop 수준이다. 재시도 정책, backoff, dead-letter queue, structured metrics, correlation ID가 보이지 않는다.

영향:

- schema evolution이 점점 위험해진다.
- 외부 API 일시 장애와 anchor 실패를 구분하기 어렵다.
- "실패했다"는 사실만 남고 "왜 얼마나 자주 어디서 실패했는가"가 남지 않는다.

#### M3. reviewer feedback learning 경로가 없다

현재 설계에는 reviewer가 resolve/unresolve/reply한 정보를 봇이 회수해 다음 run의 suppression 또는 scoring에 반영하는 경로가 없다. 이 상태에서는 노이즈를 줄이는 유일한 수단이 코드 수정이나 threshold 조정뿐이 된다.

영향:

- 시간이 지나도 팀의 리뷰 선호를 학습하지 못한다.
- false positive를 운영적으로 줄이기 어렵다.

### 3.3 Low Severity

#### L1. naming/config/runbook hygiene가 아직 거칠다

예를 들어 `pr_id`는 실제로는 GitLab MR `iid`이고, 문서에서는 project-level 확장 이야기가 나오지만 코드 모델에는 반영되지 않는다. local bootstrap/runbook도 서비스 분리 의도에 비해 저장소 경계가 덜 정리되어 있다.

이 문제만으로 시스템이 망가지는 것은 아니지만, 앞으로 재설계를 시작할 때 오해 비용이 커진다.

## 4. 외부 리뷰 봇 비교 매트릭스

아래 비교는 "누가 더 좋다"가 아니라 "우리 시스템이 어떤 패턴을 배워야 하는가"를 보기 위한 것이다.

| 제품 | 자동 리뷰 트리거 | 컨텍스트 전략 | 출력 형태 | 신뢰도/노이즈 제어 | 운영/보안 관점 | 우리에게 중요한 시사점 |
| --- | --- | --- | --- | --- | --- | --- |
| GitLab Duo | MR review 요청, 자동 리뷰, draft에서 ready 전환 후 리뷰 | 코드 변경, MR 코멘트, linked issue, repo 구조, custom review instructions, context exclusions | inline comment, summary, review flow session | custom instructions와 GitLab-native context를 사용 | GitLab.com, Self-Managed, Dedicated 지원 축이 강함 | GitLab-first라면 thread lifecycle과 review instruction 모델을 가장 직접적으로 벤치마크할 가치가 큼 |
| CodeRabbit | 자동 리뷰, push별 incremental review, manual full/incremental review, commit threshold auto-pause | path instructions, guideline reference, cache, linked issue/PR context | summary, inline, autofix, manual commands | incremental/full 분리, auto-pause, path filter, resolve command, review cache | self-hosted GitLab 문서가 명확하고 token scope도 구체적 | 우리도 incremental/full 구분, commit threshold pause, comment resolve/update를 가져와야 함 |
| Qodo | PR open/update/ready 자동 리뷰, `/agentic_review` 수동 리뷰 | dynamic context, ticket context, ignore/exclusion, PR history 기반 rule suggestion | summary, inline, both, remediation guidance | self-reflection, score threshold, code validation, hierarchical presentation | on-premise와 GitLab 지원 축이 보이며 규칙 시스템이 강함 | 탐지 후 self-reflection과 validation을 거쳐 게시하는 패턴을 배울 가치가 큼 |
| GitHub Copilot Code Review | 자동 PR review 설정, 수동 review 요청 | repository-wide/path-specific custom instructions, excluded files | PR review comment 중심 | excluded file 정책, path-specific instructions | GitHub-native | path별 지침과 전역 지침을 분리하는 구성 모델이 단순하고 실용적 |
| Sonar Review | PR create/update, comment trigger, draft는 ready 후 자동 리뷰 | deterministic static analysis + AI, PR analysis 결과 활용 | inline, summary, walkthrough, diagram | 정적 분석과 AI 결합, quality gate, analysis 실패 시 AI-only fallback | GitHub 중심, 추가 인프라 없이 Sonar 플랫폼 내부 처리 | "탐지"는 deterministic, "설명"은 AI라는 분업이 가장 명확함 |
| Amazon Q Developer | 새 PR/재오픈 PR 자동 리뷰, `/q review` 수동 재리뷰, subsequent push 자동 재리뷰는 제한적 | 전체 PR diff, `.amazonq/rules` 기반 custom coding standards | summary, threaded findings, fix suggestion | 자동 리뷰 + 수동 재리뷰 분리, custom rules | GitHub 중심, preview 기능 포함 | 항상 모든 push를 자동 리뷰하기보다 on-demand rerun 모델을 섞는 접근이 참고할 만함 |
| Snyk PR Checks / PR Experience | PR code change 시 check, integration-level 설정 | 보안/코드 분석 결과, severity 기준, ignore state | status check, summary comment, inline comment, fix command | severity gate, ignored finding collapse/resolve, commit push 시 summary update | GitLab 포함 다수 SCM 지원이나 GitLab inline에는 제약이 명시됨 | 리뷰 봇도 comment lifecycle과 severity gate를 분리해 가져가야 함 |

외부 비교에서 공통적으로 보이는 패턴은 아래와 같다.

- 성숙한 봇은 "모든 것을 LLM에게 묻지 않는다."
- 대부분 탐지와 설명을 분리한다.
- 대부분 full review와 incremental review를 구분하거나, 최소한 noisy re-review를 제어한다.
- 대부분 path-specific instruction, custom rule, exclusion 정책을 제공한다.
- 대부분 thread lifecycle을 1회 게시가 아니라 업데이트/해결/동기화 대상으로 본다.
- 강한 제품일수록 status gate, severity threshold, validation, self-reflection 같은 신뢰도 제어 장치를 갖는다.

## 5. 현재 방향 유지 여부 판단

### 5.1 방향 수준 판단

`external Git UI -> review-bot -> review-engine` 자체는 맞다.

이 방향이 맞는 이유는 다음과 같다.

- 기존 Git UI를 canonical surface로 두면 개발자가 새로운 리뷰 툴 UI를 배우지 않아도 된다.
- review-bot이 adapter/orchestrator를 맡으면 SCM별 차이를 한 층에서 흡수할 수 있다.
- review-engine이 규칙 지식과 탐지에 집중하면, GitLab/GitHub/Gerrit 같은 게시 채널과 느슨하게 결합할 수 있다.

즉, 계층 분리 철학은 버릴 이유가 없다.

### 5.2 구현 수준 판단

현재 구현 상태는 "방향은 맞지만, 그대로 키우면 부채가 더 빨리 커지는 단계"다.

판단 요약:

- 방향: 유지 가능
- 현재 adapter 계약: 유지 불가
- 현재 key model: 유지 불가
- 현재 package/workspace 경계: 유지 불가
- 현재 detector/score/publish 결합 방식: 일부 유지 가능하나 재배치 필요
- 현재 LLM 위치: 1차 탐지기보다 설명기 역할로 후퇴시키는 것이 바람직

### 5.3 선택지 비교

#### 옵션 1. 현 구조 유지 + 운영 하드닝

장점:

- 가장 빠르다.
- 현재 코드 재사용률이 높다.

한계:

- `pr_id` 단일 키, adapter 빈약성, thread-state 부재 같은 구조 문제를 남긴다.
- 문서/런타임 drift를 조금 줄여도 lifecycle debt는 계속 쌓인다.

적합한 경우:

- 단일 GitLab 프로젝트, 단기 실험, low-risk pilot

#### 옵션 2. 규칙/판정/설명 계층을 분리하는 하이브리드 재설계

장점:

- 현재 엔진/봇 자산을 살리면서도 운영형 계약으로 승격할 수 있다.
- false positive 제어를 구조적으로 넣을 수 있다.
- GitLab-first이면서도 GitHub/Gerrit 이식성이 높다.

단점:

- 1~2 sprint 수준의 설계/마이그레이션 작업이 필요하다.
- 데이터 모델 변경과 adapter 전면 수정이 따른다.

적합한 경우:

- 내부 규칙이 강하고, 외부 상용 봇으로 완전히 대체하기 어렵고, 장기 운영 의지가 있는 경우

#### 옵션 3. 외부 리뷰 봇 도입 또는 혼합 운영

장점:

- incremental review, custom instructions, autofix, status gate 같은 기능을 빠르게 확보할 수 있다.
- 운영 기능 성숙도가 높다.

단점:

- Altibase 내부 규칙과 조직 특화 문맥을 완벽히 옮기기 어렵다.
- 데이터 보관, self-hosted, 비용, governance 이슈가 생긴다.

적합한 경우:

- 보안/품질/범용 베스트프랙티스는 상용 도구에 맡기고, 내부 규칙만 자체 엔진으로 유지하려는 경우

최종 판단:

- 단독 권고안은 옵션 2다.
- 다만 보안/정적 분석 영역은 Sonar/Snyk 같은 외부 도구와 혼합 운영하는 것이 더 낫다.

## 6. 권고 재설계안

### 6.1 목표 원칙

- SCM은 canonical state owner다.
- bot은 orchestration, sync, publishing, learning을 맡는다.
- engine은 detection/evidence/policy metadata를 제공한다.
- LLM은 publishing-ready explanation을 만든다.
- 게시 이후 thread state는 다시 데이터로 회수된다.

### 6.2 목표 파이프라인

```text
Webhook/Event Intake
-> Identity Normalize
-> Diff Fetch + Context Resolve
-> Detect
-> Validate
-> Score
-> Explain
-> Publish
-> Learn
```

각 단계의 책임은 아래처럼 나누는 것이 좋다.

- `detect`
  - 규칙, diff pattern, static signal, repository metadata를 바탕으로 candidate finding을 생성
- `validate`
  - changed-line anchor 유효성, reviewability, SCM capability, rule policy, duplicate candidate 검증
- `score`
  - severity, confidence, novelty, historical false-positive, batch diversity를 반영해 게시 우선순위 산정
- `explain`
  - LLM이 reviewer-friendly 한국어 설명, 수정 방향, 왜 중요한지 생성
- `publish`
  - inline thread upsert, summary refresh, status/check publish
- `learn`
  - resolve/unresolve/reply/ignore/reaction을 회수해 suppression과 rerank에 반영

### 6.3 권고 인터페이스

현재 `pr_id` 단일 키는 아래 composite identity로 바꾸는 것이 좋다.

```text
ReviewRequestKey {
  review_system: "gitlab" | "github" | "gerrit" | ...,
  project_ref: string,
  review_request_id: string
}
```

adapter 계약은 최소 아래 수준으로 확장해야 한다.

```text
fetch_review_request_meta(key)
fetch_diff(key)
list_threads(key)
upsert_comment(key, finding, anchor, body)
resolve_thread(key, thread_ref)
publish_status(key, state, description, details?)
collect_feedback(key)
```

여기서 중요한 점은 `post_comment`보다 `upsert_comment`다. 운영형 봇은 "새 코멘트를 달 것인가"보다 "기존 코멘트를 업데이트할 것인가, stale 처리할 것인가, 해결할 것인가"가 더 중요하다.

### 6.4 권고 데이터 모델

현재 `ReviewFinding` 하나에 너무 많은 역할이 몰려 있다. 아래처럼 책임을 나누는 편이 좋다.

- `FindingEvidence`
  - detector가 본 diff snippet, line candidates, matched patterns, source evidence
- `FindingDecision`
  - rule id, severity, confidence, dedupe key, suppression reason, publish eligibility
- `PublicationState`
  - current comment id, published body hash, batch no, publish error, last published at
- `ThreadSyncState`
  - thread id, resolved 여부, stale 여부, reviewer interaction, last synced at

이렇게 나누면 "탐지"와 "게시"와 "운영 상태"를 독립적으로 다룰 수 있다.

### 6.5 LLM 역할 재배치

현재 구조에서도 LLM/provider는 최종 문구 생성에 가깝지만, 전체 체인에서 차지하는 비중이 아직 크다. 권장 방향은 더 명확하다.

- detector는 규칙/패턴/정적 분석 중심
- scorer는 확률과 정책 중심
- LLM은 최종 reviewer message와 fix explanation 중심

즉, LLM이 처음부터 "문제가 있는지"를 판정하는 것이 아니라, 이미 좁혀진 고신뢰 finding을 사람이 읽기 좋은 언어로 바꿔 주는 역할을 맡는 것이 좋다.

이렇게 해야 하는 이유는 명확하다.

- false positive 제어가 쉬워진다.
- 규칙 시스템과 평가 harness를 만들기 쉬워진다.
- 보안/품질 도구와 결합하기 쉽다.
- GitLab inline thread 운영과 더 잘 맞는다.

### 6.6 노이즈 억제 전략

권고안의 핵심 acceptance 기준 중 하나는 노이즈 억제다. 아래 항목은 구조로 구현해야 한다.

- `manual_only`와 `reference_only`는 detect 단계에서 candidate는 만들되 publish 대상에서는 기본 제외
- full review와 incremental review를 구분
- commit threshold pause 도입
- reviewer가 resolve한 동일 fingerprint는 일정 기간 suppression
- path/class/rule별 custom instruction 적용
- stale thread는 새 comment 생성보다 update/resolve 우선
- batch diversity를 유지해 한 파일/한 규칙만 반복되지 않게 함
- inline anchor 불확실 시 무분별한 general note fallback 금지

## 7. 단계별 개선 로드맵

### 7.1 0-30일: 정확도와 운영 위험 제거

- `ide_rc_flow` 계약 실패를 우선 해결한다.
- diff manifest 기대값과 extractor 로직 중 무엇이 정답인지 정리하고 테스트를 고친다.
- 문서(`API_CONTRACTS`, `OPERATIONS_RUNBOOK`)를 실제 구현과 맞춘다.
- `pr_id` 단일 키를 즉시 없애지 못하더라도 `review_system`, `project_ref`, `review_request_id`를 수용할 준비 필드를 추가한다.
- migration 체계를 도입한다. 최소 Alembic 같은 schema migration 경로가 필요하다.
- worker에 retry/backoff/log correlation id를 붙인다.
- publish 실패 원인을 분류한다. 예를 들어 anchor failure, GitLab API failure, auth failure, validation failure를 구분 기록한다.
- 패키지 경계 문제를 정리한다. 최소한 루트와 하위 프로젝트의 `app` namespace 충돌은 멈춰야 한다.

이 단계의 완료 기준:

- `review-bot` 테스트 green 유지
- `review-engine` 계약 테스트 green 복구
- 루트/서브프로젝트 실행 경계가 문서화되고 재현 가능
- 운영 문서와 실제 adapter 동작 불일치 해소

### 7.2 30-90일: adapter/thread lifecycle 재설계

- adapter v2를 도입한다.
- `list_threads`, `upsert_comment`, `resolve_thread`, `publish_status`, `collect_feedback`를 구현한다.
- `PublicationState`와 `ThreadSyncState` 테이블을 도입한다.
- 게시 후 reconcile job을 추가해 resolved/stale/open 상태를 주기적으로 동기화한다.
- batch publish와 thread update를 분리한다.
- current GitLab adapter의 `project_id` 단일 env 의존을 review request 단위 lookup으로 바꾼다.
- provider/LLM 위치를 `score` 뒤로 명확히 내린다.

이 단계의 완료 기준:

- 동일 finding 재게시율 감소
- resolved thread 자동 동기화
- GitLab inline discussion과 status publishing 계약이 명시됨
- 멀티 프로젝트 MR 동시 처리 가능

### 7.3 90일+: feedback loop와 평가 체계 구축

- reviewer resolve/reply/ignore 데이터를 scoring에 반영한다.
- gold diff set과 regression harness를 만든다.
- rule family별 precision/recall proxy를 추적한다.
- multi-project/multi-SCM identity를 실제 운영에 투입한다.
- 필요시 Sonar/Snyk와 같은 deterministic/security 계열 도구와 혼합 운영한다.

이 단계의 완료 기준:

- false positive 회귀를 측정 가능한 수준으로 관리
- 신규 rule 추가 시 evaluation harness 통과가 기본 절차가 됨
- GitLab 외 review system 확장 시 adapter 추가만으로 대응 가능

## 8. 부록: 테스트/문서/코드 근거

### 8.1 저장소 근거 요약

- 아키텍처 방향
  - `docs/WORKSPACE_SPLIT_ARCHITECTURE.md`
  - `External Git Review System ---> review-bot ---> review-engine`
- adapter 문서 계약
  - `docs/API_CONTRACTS.md`
  - `get_pull_request_diff`, `post_comment`, `post_status`만 명시
- 운영 문서 상태
  - `docs/OPERATIONS_RUNBOOK.md`
  - GitLab adapter를 여전히 summary note 중심 MVP로 설명
- 실제 GitLab adapter 구현
  - `review-bot/app/review_systems/gitlab.py`
  - inline discussion 게시 시도 존재
  - commit status는 아직 stub
- DB key 모델
  - `review-bot/app/db/models.py`
  - `ReviewRun`, `ReviewFinding`, `FindingPublication` 모두 `pr_id` 중심
- webhook 정책
  - `review-bot/app/api/main.py`
  - `update`인데 `oldrev`가 없으면 `merge_request_update_without_new_commits`로 무시
- detector 계약
  - `review-engine/app/query/cpp_feature_extractor.py`
  - `ide_rc_flow`는 `IDE_RC`만으로는 생성되지 않고 flow signal regex를 요구
- reviewability gating
  - `review-engine/app/models.py`
  - `auto_review`, `manual_only`, `reference_only` 보유
  - `review-engine/app/ingest/build_records.py`
  - 외부 rule을 `reference_only` 또는 `manual_only`로 내리는 로직 보유

### 8.2 테스트 실행 결과

실행 일시: 2026-04-20

명령:

```bash
cd review-bot && uv run --extra dev python -m pytest -q
cd review-engine && uv run --extra dev python -m pytest -q
```

결과:

- `review-bot`: `25 passed in 1.71s`
- `review-engine`: `1 failed, 48 passed in 2.43s`

실패 항목:

```text
FAILED tests/test_altidev4_diff_contract.py::test_altidev4_diff_manifest_focus_patterns_are_detected
missing focus pattern ide_rc_flow
```

### 8.3 요청하신 검증 시나리오와 저장소 근거 연결

| 검증 시나리오 | 현재 근거 |
| --- | --- |
| GitLab large diff 누락 시 patch 재구성 | `review-bot/tests/test_gitlab_adapter.py`에서 large new file diff 생략 시 raw file을 읽어 patch를 재구성하는 테스트 존재 |
| MR update without new commit 무시 정책 | `review-bot/tests/test_api_queue.py`에서 `merge_request_update_without_new_commits` 검증 |
| 동일 hunk/다중 hunk dedupe와 line anchor 정확도 | `review-bot/tests/test_review_runner.py`에 dedupe, changed-line targeting, large hunk split, diversity batching 테스트 존재 |
| `ide_rc_flow` 패턴 누락처럼 detector 계약이 깨지는 경우 | 현재 `review-engine` 테스트가 실제로 이 케이스에서 실패 |
| manual-only/reference-only 규칙이 자동 게시로 새어 나오지 않는지 | `review-engine/app/models.py`, `review-engine/app/ingest/build_records.py`, `review-engine/data/review_profiles.json`에서 gating 모델 확인 가능 |
| inline discussion 게시 실패 시 general note로 무분별 fallback 하지 않는지 | `review-bot/tests/test_review_runner.py`에 명시적 테스트 존재 |
| 멀티 프로젝트에서 동일 `iid` 충돌 가능성 | DB가 `pr_id` 단일 정수 중심이고 GitLab adapter가 `project_id` 단일 env에 의존하므로 구조적 리스크 존재 |
| 루트/서브프로젝트 실행 시 패키지 충돌과 테스트 분리 문제 | 루트/하위 `pyproject.toml`가 모두 `app` 패키지를 사용하며, 루트 기준 `uv run --project review-bot ...` 실행 시 import 충돌과 의존성 혼선 확인 |

### 8.4 현재 구현에서 유지할 만한 좋은 점

- diff 누락 복구
- webhook noise suppression
- reviewability metadata
- anchor precision 우선 정책
- inline anchor 실패 시 general note fallback 금지
- dedupe 및 batch diversity

즉, 이 시스템은 "다시 처음부터"보다 "좋은 부분을 보존한 재설계"가 더 맞다.

### 8.5 외부 공식 문서 참고

- GitLab Duo contextual awareness
  - https://docs.gitlab.com/user/gitlab_duo/context/
- GitLab Duo review instructions
  - https://docs.gitlab.com/user/gitlab_duo/customize_duo/review_instructions/
- GitLab Duo Code Review Flow
  - https://docs.gitlab.com/user/duo_agent_platform/flows/foundational_flows/code_review/
- GitLab Duo in merge requests
  - https://docs.gitlab.com/user/project/merge_requests/duo_in_merge_requests/
- CodeRabbit automatic review controls
  - https://docs.coderabbit.ai/configuration/username-based-pr-review-control
- CodeRabbit path instructions
  - https://docs.coderabbit.ai/configuration/path-instructions
- CodeRabbit review commands
  - https://docs.coderabbit.ai/guides/commands
- CodeRabbit self-hosted GitLab
  - https://docs.coderabbit.ai/platforms/self-hosted-gitlab
- CodeRabbit caching
  - https://docs.coderabbit.ai/reference/caching
- Qodo dynamic context
  - https://docs.qodo.ai/qodo-documentation/qodo-merge/pr-agent/core-abilities/dynamic_context
- Qodo self-reflection
  - https://docs.qodo.ai/qodo-documentation/qodo-merge/pr-agent/core-abilities/self_reflection
- Qodo code validation
  - https://docs.qodo.ai/qodo-documentation/qodo-merge/pr-agent/core-abilities/code_validation
- Qodo use in PRs
  - https://docs.qodo.ai/qodo-documentation/code-review/get-started/use-qodo-in-prs
- GitHub Copilot code review overview
  - https://docs.github.com/copilot/concepts/code-review
- GitHub Copilot code review usage
  - https://docs.github.com/copilot/using-github-copilot/code-review/using-copilot-code-review
- GitHub Copilot custom instructions
  - https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot
- Sonar Review
  - https://docs.sonarsource.com/sonarqube-cloud/ai-capabilities/sonar-review
- SonarQube Cloud pull request analysis
  - https://docs.sonarsource.com/sonarqube-cloud/improving/pull-request-analysis/
- Amazon Q Developer code reviews in GitHub
  - https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/github-code-reviews.html
- Snyk pull request checks
  - https://docs.snyk.io/scan-with-snyk/pull-requests/pull-request-checks
- Snyk configure pull request checks
  - https://docs.snyk.io/scan-with-snyk/pull-requests/pull-request-checks/configure-pull-request-checks
- Snyk pull request experience
  - https://docs.snyk.io/scan-with-snyk/pull-requests/pull-request-checks/pull-request-experience

## 최종 결론

이 방향은 "틀렸다"기보다 "아직 운영형 구조로 덜 완성됐다"가 더 정확하다.

따라서 권고는 명확하다.

- `external Git UI -> review-bot -> review-engine` 분리는 유지한다.
- `ReviewSystemAdapter`, key model, thread lifecycle, migration/observability는 재설계한다.
- LLM은 탐지기보다 설명기로 재배치한다.
- 외부 도구는 대체재가 아니라, 정적/보안 영역에서의 보강재로 검토한다.

이렇게 가면 현재 자산을 버리지 않으면서도 더 좋은 리뷰 봇으로 진화시킬 수 있다.
