# Review System Adapter Capability Matrix

## 목적

이 문서는 `ReviewSystemAdapterV2` 기준으로 GitLab 외 SCM 확장을 준비하기 위한 capability matrix를 고정한다.

## V2 Contract

- `fetch_review_request_meta`
- `fetch_diff`
- `list_threads`
- `upsert_comment`
- `resolve_thread`
- `publish_check`
- `collect_feedback`

## 현재 상태

| Capability | GitLab | GitHub | Gerrit |
| --- | --- | --- | --- |
| review request meta | 구현 | 설계 필요 | 설계 필요 |
| diff fetch | 구현 | 설계 필요 | 설계 필요 |
| incremental compare base | 구현 | 설계 필요 | 설계 필요 |
| inline thread create | 구현 | 설계 필요 | 설계 필요 |
| existing thread update/reply | 구현 | 설계 필요 | 설계 필요 |
| resolved thread reopen | 구현 | 설계 필요 | 설계 필요 |
| thread resolve | 구현 | 설계 필요 | 설계 필요 |
| status/check publish | 구현 | 설계 필요 | 설계 필요 |
| feedback collect | 구현 | 설계 필요 | 설계 필요 |
| pagination handling | 구현 | 설계 필요 | 설계 필요 |
| large diff patch rebuild | 구현 | 설계 필요 | 설계 필요 |

## SCM별 차이 메모

### GitLab

- merge request discussion이 lifecycle의 중심이다.
- thread resolve/unresolve와 inline position이 API에 직접 드러난다.
- current-state는 GitLab-first 운영을 기준으로 구현되어 있다.

### GitHub

- review comment와 review thread, check run/status, PR review가 분리되어 있다.
- thread resolution과 comment mutation API 차이를 별도 adapter policy로 풀어야 한다.

### Gerrit

- change / patchset / comment 구조가 merge-request형 UI와 다르다.
- `review_request_id`와 `head_sha`의 의미를 patchset 중심으로 다시 매핑해야 한다.

## 추상화 원칙

1. domain identity는 SCM 공통으로 `ReviewRequestKey`를 유지한다.
2. comment/thread lifecycle은 adapter가 흡수하고, `review-bot`은 fingerprint / anchor / lifecycle 정책만 본다.
3. SCM별 status/check 차이는 `publish_check`가 숨긴다.
4. feedback 수집은 최소 공통분모를 `resolved`, `unresolved`, `reply`로 둔다.

## 다음 확장 순서

1. GitHub adapter
2. Gerrit adapter

이유:

- GitHub는 thread/status 개념이 GitLab과 상대적으로 가깝다.
- Gerrit은 patchset 중심 모델이라 domain mapping 비용이 더 크다.
