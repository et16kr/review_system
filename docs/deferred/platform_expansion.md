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

### GitHub Adapter Readiness Packet

이 packet은 GitHub adapter 구현을 시작하기 전 고정해야 할 최소 차이만 정리한다.
구현은 아직 deferred이며, 아래 내용은 live GitHub smoke 성공이나 GitHub adapter 존재를 뜻하지 않는다.

#### GitLab / GitHub Adapter Difference Matrix

| Surface | GitLab current adapter | GitHub first adapter design |
| --- | --- | --- |
| Business identity | `review_system=gitlab`, `project_ref=project.path_with_namespace`, `review_request_id=merge_request.iid` | `review_system=github`, `project_ref=repository.full_name`, `review_request_id=pull_request.number` 문자열 |
| Review trigger webhook | GitLab `Note Hook` 중 MR note line-start `@review-bot` 또는 `/review-bot` 명령만 enqueue | GitHub `issue_comment.created` 중 pull request conversation comment의 line-start `@review-bot` 또는 `/review-bot` 명령만 enqueue |
| Automatic PR/MR updates | MR open/update는 review를 자동 시작하지 않음 | `pull_request` open/synchronize/reopened는 state refresh signal로만 보고 review 자동 시작은 하지 않음 |
| Metadata | MR API의 title/state/draft/source/target/diff refs를 `ReviewRequestMeta`로 변환 | Pulls API의 title/state/draft, base/head refs와 `base.sha`/`head.sha`를 `ReviewRequestMeta`로 변환 |
| Full diff | MR changes API의 `changes[].diff`와 `diff_refs` | PR files API의 `filename`, `previous_filename`, `status`, `patch`, additions/deletions와 PR base/head SHA |
| Incremental diff | `base_sha`가 있으면 compare API로 previous head -> current head 변경분 재구성 | `base_sha`가 있으면 commits compare API로 previous head -> current PR head 변경분 재구성 |
| Inline thread model | GitLab discussion id가 thread, first note id가 root comment | GitHub review thread node id를 thread로 보고, root review comment id/node id를 reply target으로 보존 |
| Inline comment create/update | discussion create, existing discussion reply, resolved discussion reopen | review comment create for new thread, review comment reply for existing thread; resolved thread reopen/resolve는 GraphQL review thread mutation 필요 |
| General note | MR notes API와 same-purpose marker upsert | PR issue comments API와 same-purpose marker upsert |
| Feedback collect | MR discussion notes에서 human replies, resolve state, feedback commands 수집 | review comments/review thread state와 `pull_request_review_comment`/`pull_request_review_thread` events 또는 polling result에서 human replies, resolve state, feedback commands 수집 |
| Status surface | commit status API on MR head SHA | first slice는 commit status on PR head SHA로 parity 유지; richer Checks API/check annotations는 separate capability로 둠 |
| Remote ref scope | thread/comment/event refs는 `ReviewRequestKey` 안에서 request-scoped unique | GitHub node ids/database ids도 storage에서는 request-scoped remote refs로만 취급하고 adapter-specific global uniqueness에 의존하지 않음 |

#### Fixture, Token, Permission Requirements

GitHub live smoke는 local GitLab smoke와 다른 external-service signal이다.
roadmap automation은 GitHub credentials가 없으면 GitHub adapter 구현/validation unit을 blocked로 남기고,
deterministic replay fixture나 docs validation만으로 live adapter success를 주장하지 않는다.

최소 fixture 경로:

1. 전용 GitHub test repository를 준비하고 base branch와 feature branch가 있는 open PR을 만든다.
2. webhook replay만 먼저 검증할 수 있도록 `issue_comment.created`,
   `pull_request_review_comment.created`, `pull_request_review_thread.resolved` payload를 redacted fixture로
   보존하고, unresolved/reopen 상태는 polling 또는 explicit GraphQL read path로 검증한다.
3. live smoke를 켤 때는 webhook secret, bot identity, installation/repository id, repository full name,
   PR number, base/head SHA를 artifact에 남긴다.
4. live smoke는 baseline review, human reply feedback, resolve/sync, status publication을 별도 신호로
   기록하며, local GitLab lifecycle smoke 성공과 섞지 않는다.

권한 기준:

- GitHub App installation token을 기본 경로로 본다. fine-grained PAT는 replay 또는 임시 smoke용
  fallback으로만 취급한다.
- required read permissions:
  - Metadata read
  - Pull requests read
  - Contents read, `fetch_file_content`와 same-file context를 켤 때 필요
- required write permissions for first live adapter:
  - Pull requests write, inline review comments/replies에 필요
  - Commit statuses write, first-slice `publish_check` parity에 필요
  - Issues write, PR conversation comments 기반 general note/help/unknown-command upsert에 필요
- optional future permission:
  - Checks write, Checks API/check annotations를 `publish_check` 대체 surface로 도입할 때만 필요
- webhook subscriptions:
  - `issue_comment`
  - `pull_request`
  - `pull_request_review_comment`
  - `pull_request_review_thread` resolved events
  - optional future `check_run` only if requested actions or rerun UX is introduced

#### `ReviewSystemAdapterV2` Extension Boundary

GitHub first slice는 `ReviewSystemAdapterV2`의 required methods를 늘리지 않는다.
adapter별 차이는 adapter 내부 API mapping과 webhook handler에서 흡수한다.

허용하는 extension point:

- existing optional `fetch_file_content`, `post_general_note`, `upsert_general_note`
- existing runner-level optional branch head settle probe와 같은 좁은 adapter capability
  (`fetch_branch_head_sha`)가 필요하면 protocol에 문서화한 뒤 GitLab/GitHub 모두 같은 의미로 맞춘다.
- `publish_check` 내부 구현이 commit status인지 Checks API인지 드러내는 adapter metadata는
  lifecycle/finding evidence의 provider runtime과 섞지 않고 review-system metadata로 둔다.
- GraphQL node id, database id, REST URL 같은 GitHub-specific ids는 adapter `raw` payload나
  request-scoped remote ref로만 보존한다.

허용하지 않는 것:

- GitHub 전용 DB table 또는 lifecycle analytics schema fork
- GitHub 자동 PR update review trigger를 GitLab과 다르게 켜는 것
- GitHub global node id uniqueness를 storage dedupe contract로 올리는 것
- Checks API 도입을 inline comment/thread sync 구현과 같은 unit에 묶는 것

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
