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

## GitLab Bot Follow-up

날짜: 2026-04-20

대상 범위:

- `review-bot/app/`
- `ops/scripts/attach_local_gitlab_bot.py`
- `ops/scripts/bootstrap_local_gitlab_tde_review.py`

### 1. High

대상:
- [attach_local_gitlab_bot.py](/home/et16/work/review_system/ops/scripts/attach_local_gitlab_bot.py:451)

문제:
- GitLab MR 코멘트 작성 주체가 `root` 관리자 계정으로 남아 있었다.
- 이 상태에서는 운영 권한 분리가 되지 않고, 리뷰 흔적도 서비스 계정이 아니라 관리자 활동처럼 보였다.

영향:
- 관리자 토큰이 런타임에 과도하게 노출될 수 있었다.
- MR discussion author가 봇 전용 계정이 아니라 `root`로 표시됐다.

수정:
- `review-bot` 비관리자 계정을 생성/갱신하도록 attach 흐름을 바꿨다.
- 프로젝트 권한은 `Developer`로 고정했고, 런타임 `GITLAB_TOKEN`은 `review-bot` PAT로 교체했다.
- 실제 GitLab MR `!2`에서 discussion author가 `review-bot`으로 보이는 것까지 확인했다.

상태:
- 해결 완료

### 2. High

대상:
- [review_runner.py](/home/et16/work/review_system/review-bot/app/bot/review_runner.py:317)
- [change_analysis.py](/home/et16/work/review_system/review-bot/app/providers/change_analysis.py:1)

문제:
- 코멘트가 hunk 시작 줄에 붙거나, provider가 잘못된 줄 번호를 반환해도 그대로 게시될 가능성이 있었다.

영향:
- inline discussion이 실제 수정 위치와 어긋날 수 있었다.
- 같은 hunk 안에서 코멘트 신뢰도가 떨어질 수 있었다.

수정:
- diff hunk를 changed line 후보 집합으로 다시 파싱하도록 변경했다.
- provider는 후보 줄 번호 안에서만 `line_no`를 선택할 수 있게 했고, 잘못된 값이면 deterministic fallback이 실제 changed line으로 보정하도록 했다.
- `continue` 예제와 invalid line 반환 예제를 테스트로 추가했다.

상태:
- 해결 완료

### 3. Medium

대상:
- [stub_provider.py](/home/et16/work/review_system/review-bot/app/providers/stub_provider.py:21)
- [ops/.env.example](/home/et16/work/review_system/ops/.env.example:27)

문제:
- stub 코멘트 본문에 표시하는 “문제로 보이는 코드” 힌트가 선택된 줄이 아니라 hunk 첫 줄을 가리킬 수 있었다.
- 또한 `.env`의 bot 비밀번호 기본값에 `$`가 들어 있어 Docker Compose가 변수 치환 경고를 냈다.

영향:
- 코멘트는 inline으로 붙어도 본문 힌트가 다른 줄을 설명할 수 있었다.
- 로컬 운영 스크립트 재실행 시 불필요한 compose 경고가 발생했다.

수정:
- stub provider가 선택된 `line_no` 주변 코드 한 줄을 우선 힌트로 쓰도록 바꿨다.
- bot 비밀번호 기본값은 Compose-safe 문자열로 교체했다.
- 실제 MR `!2`에서 코멘트 본문 힌트가 선택 줄과 맞아지는 것까지 확인했다.

상태:
- 해결 완료

### 4. Medium

대상:
- [stub_provider.py](/home/et16/work/review_system/review-bot/app/providers/stub_provider.py:21)
- [review_runner.py](/home/et16/work/review_system/review-bot/app/bot/review_runner.py:52)
- [change_analysis.py](/home/et16/work/review_system/review-bot/app/providers/change_analysis.py:1)

문제:
- GitLab MR `!2`를 실제로 다시 달아 보니 두 가지가 남아 있었다.
- 하나는 영어 `fix_guidance` 문장이 그대로 코멘트에 섞여 자연스러운 리뷰 톤을 깨는 문제였다.
- 다른 하나는 changed line에 직접 신호가 없는 규칙형 finding이 파일 첫 줄 같은 어색한 위치에 anchor 될 수 있다는 점이었다.

영향:
- 코멘트가 기계적으로 보이거나 팀 내 자연스러운 리뷰 문체와 어긋날 수 있었다.
- 실제 수정 위치가 아닌 곳에 discussion이 달려 신뢰도를 떨어뜨릴 수 있었다.

수정:
- 영어/원문 지침은 stub 코멘트에 그대로 노출하지 않도록 정리했다.
- 직접 신호가 필요한 issue는 changed line에서 실제 토큰이 잡히는 경우에만 게시하고, 그렇지 않으면 생략하도록 보수적으로 바꿨다.
- 같은 줄에 사실상 같은 메시지가 중복되는 경우를 막기 위해 human-readable message 기반 dedupe를 추가했다.
- 관련 회귀 테스트를 추가해 `18 passed` 기준으로 고정했다.

상태:
- 해결 완료

## 최신 결론

현재 기준으로 GitLab 연동 경로의 핵심 위험 요소는 정리됐다.

- MR은 기존 것 대신 새 `tde_first -> tde_base` `!2`만 남아 있다.
- 첫 배치 코멘트 5개는 모두 `review-bot` 계정이 남겼다.
- 코멘트는 `DiffNote`로 붙고, 규칙 ID 대신 자연스러운 설명과 수정 제안 중심으로 렌더링된다.
- 실제 MR 재검수 기준으로 영어 안내 누출과 어색한 line 1 anchor는 제거됐다.

## GitLab Bot Tuning Follow-up

날짜: 2026-04-20

대상 범위:

- `review-engine/app/`
- `review-engine/data/review_profiles.json`
- `review-bot/app/`

### 1. High

대상:
- [review_profiles.json](/home/et16/work/review_system/review-engine/data/review_profiles.json:11)
- [search.py](/home/et16/work/review_system/review-engine/app/retrieve/search.py:31)
- [applicability.py](/home/et16/work/review_system/review-engine/app/retrieve/applicability.py:1)

문제:
- 자동 리뷰 후보에 오류 처리 스타일 규칙이 너무 넓게 섞여 들어왔다.
- 실제로는 선언부나 `IDE_TEST_RAISE` 같은 내부 패턴만 보여도 관련 규칙이 잡혔고,
  bot이 이를 자연어 코멘트로 바꾸면서 “문제가 확인된 코드”처럼 보이게 만들었다.

영향:
- MR `!2`에 선언부/반환문/예외 처리 매크로만 보고 달리는 추상적인 코멘트가 생길 수 있었다.
- 사용자가 “무엇이 실제 문제인지”를 이해하기 어려운 리뷰가 나왔다.

수정:
- `ALTI-ERR` 섹션은 `manual_only`로 내려 자동 게시 대상에서 제외했다.
- 검색 결과는 pattern applicability 검증을 한 번 더 통과해야만 최종 후보가 되도록 유지했다.
- 선언만 있는 `IDE_RC` 코드와 `IDE_TEST_RAISE` 예제는 자동 리뷰 결과가 비어야 한다는 테스트를 추가했다.

상태:
- 해결 완료

### 2. High

대상:
- [change_analysis.py](/home/et16/work/review_system/review-bot/app/providers/change_analysis.py:1)
- [stub_provider.py](/home/et16/work/review_system/review-bot/app/providers/stub_provider.py:1)

문제:
- bot의 issue 분류가 코드 excerpt보다 규칙 제목/요약에 끌려가면서,
  실제 코드에 없는 문제를 있는 것처럼 확정할 수 있었다.
- `idlOS::snprintf` 같은 래퍼 호출도 `printf(` 부분 문자열 때문에 직접 libc 호출처럼 오탐할 수 있었다.

영향:
- 래퍼를 이미 쓰는 코드에 wrapper 위반 코멘트가 붙을 수 있었다.
- 오류 처리 스타일 지침이 generic natural-language 코멘트로 오해를 만들 수 있었다.

수정:
- issue 분류는 민감한 항목일수록 코드 excerpt의 직접 신호만 사용하도록 좁혔다.
- `snprintf`/`printf` 계열은 네임스페이스/래퍼 호출을 직접 libc 호출로 보지 않도록 정규식을 바꿨다.
- `ide_rc_flow`, `ide_exception_flow`는 stub 단계에서도 기본 비게시로 내려, stale 후보가 와도 외부 댓글로는 남지 않게 했다.

상태:
- 해결 완료

### 3. High

대상:
- [gitlab.py](/home/et16/work/review_system/review-bot/app/review_systems/gitlab.py:1)
- [review_runner.py](/home/et16/work/review_system/review-bot/app/bot/review_runner.py:1)

문제:
- GitLab `changes` API는 큰 신규 파일의 `diff`를 비워 보낼 수 있었다.
- 이 경우 `idsTde.cpp` 같은 핵심 신규 파일이 통째로 리뷰 대상에서 빠졌다.

영향:
- 실제 문제 가능성이 높은 신규 구현 파일이 자동 리뷰에서 완전히 누락될 수 있었다.

수정:
- GitLab adapter에 empty diff fallback을 추가했다.
- `diff`가 비어 있으면 base/head 파일 내용을 GitLab raw API로 가져와 로컬에서 unified diff를 재구성한다.
- 추가로 huge added hunk는 여러 개의 작은 review unit으로 분할해, 파일 앞부분 한 군데만 보는 문제를 줄였다.
- 관련 adapter 테스트와 review unit 분할 테스트를 추가했다.

상태:
- 해결 완료

### 4. Medium

대상:
- [review_runner.py](/home/et16/work/review_system/review-bot/app/bot/review_runner.py:169)
- [review_runner.py](/home/et16/work/review_system/review-bot/app/bot/review_runner.py:309)

문제:
- 배치 게시가 점수순 단순 상위 5개라서, 같은 파일의 같은 종류 지적이 한 배치에 반복될 수 있었다.

영향:
- 리뷰 첫 화면이 다양한 문제보다 같은 메모리 지적만 여러 개 반복되는 형태로 보일 수 있었다.

수정:
- 한 배치에서는 같은 파일의 같은 제목 코멘트를 반복 게시하지 않도록 selection을 다변화했다.
- 같은 제목은 전체 배치에서 최대 두 번까지만 허용하도록 제한해, 메모리/흐름/분기 같은 다른 종류 지적이 함께 보이게 했다.
- 회귀 테스트를 추가해 동일 file/title 반복이 억제되는 것을 고정했다.

상태:
- 해결 완료

## 최종 점검 결과

최종 MR:
- `http://127.0.0.1:18929/root/altidev4-review/-/merge_requests/2`

최종 점검 기준:
- 코멘트 작성자는 모두 `review-bot`
- 코멘트 타입은 모두 `DiffNote`
- 선언부/반환문/예외 처리 매크로만 보고 달리는 추상 코멘트는 제거됨
- 래퍼 호출 `idlOS::snprintf` 오탐은 제거됨
- 큰 신규 파일도 리뷰 대상에 포함됨
- 첫 배치는 메모리/`switch`/`continue`처럼 설명 가능한 항목으로 다양화됨

남은 관찰:
- 메모리 관련 코멘트는 아직도 heuristic 기반이라, 저수준 래퍼를 일부러 쓰는 영역에서는 사람이 한 번 더 판단하는 편이 좋다.
- OpenAI provider 쿼터가 복구되면 같은 구조에서 자연어 품질을 더 끌어올릴 수 있지만,
  현재 stub fallback 기준에서도 “무엇이 문제인지 / 어떻게 고칠지”는 충분히 읽히는 상태다.
