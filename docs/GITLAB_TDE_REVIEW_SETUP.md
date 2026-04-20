# GitLab TDE 리뷰 준비

## 목적

이 문서는 `~/work/altidev4` 저장소의 `tde_first -> tde_base` 변경을
GitLab Merge Request로 만드는 절차를 고정한다.

현재 목적은 **bot 이전 단계**로서, GitLab에 실제 리뷰 대상을 먼저 만드는 것이다.

## 현재 로컬 기준

- 저장소: `/home/et16/work/altidev4`
- source branch: `tde_first`
- target branch: `tde_base`
- diff stat: `48 files changed, 9424 insertions(+), 812 deletions(-)`

## 준비 변수

아래 값이 있으면 실제 GitLab MR을 자동으로 만들 수 있다.

```bash
export GITLAB_URL=https://gitlab.example.com
export GITLAB_TOKEN=...
export GITLAB_NAMESPACE_PATH=group-or-user
```

선택 변수:

```bash
export GITLAB_PROJECT_REF=group-or-user/altidev4
```

- `GITLAB_PROJECT_REF`가 있으면 기존 프로젝트를 사용한다.
- 없으면 `--create-project`와 `GITLAB_NAMESPACE_PATH`를 함께 사용해 새 프로젝트를 만든다.

## Dry Run

먼저 실제 API 호출 없이 준비 상태를 본다.

```bash
bash /home/et16/work/review_system/ops/scripts/create_altidev4_tde_review.sh --dry-run
```

이 명령은 아래를 보여준다.

- source/target branch
- MR title
- 기본 description 초안
- Git diff summary

## 실제 GitLab MR 생성

기존 프로젝트가 이미 있을 때:

```bash
export GITLAB_URL=https://gitlab.example.com
export GITLAB_TOKEN=...
export GITLAB_PROJECT_REF=group-or-user/altidev4

bash /home/et16/work/review_system/ops/scripts/create_altidev4_tde_review.sh
```

새 프로젝트를 만들면서 진행할 때:

```bash
export GITLAB_URL=https://gitlab.example.com
export GITLAB_TOKEN=...
export GITLAB_NAMESPACE_PATH=group-or-user

bash /home/et16/work/review_system/ops/scripts/create_altidev4_tde_review.sh --create-project
```

## 로컬 GitLab 부트스트랩

GitLab 서버가 따로 없으면, 이 워크스페이스 안에서 로컬 GitLab을 바로 띄울 수 있다.

```bash
python3 /home/et16/work/review_system/ops/scripts/bootstrap_local_gitlab_tde_review.py
```

이 스크립트는 아래를 자동으로 수행한다.

1. 로컬 GitLab 컨테이너 실행
2. root 관리자 계정 보장
3. root personal access token 생성
4. `root/altidev4` 프로젝트 생성
5. `tde_base`, `tde_first` 브랜치 push
6. `tde_first -> tde_base` Merge Request 생성

로컬 기본 접속 정보:

- GitLab URL: `http://127.0.0.1:18929`
- 프로젝트: `http://127.0.0.1:18929/root/altidev4`
- MR: `http://127.0.0.1:18929/root/altidev4/-/merge_requests/1`

로컬 root 로그인 정보는 `ops/.env`의 아래 값을 사용한다.

- `LOCAL_GITLAB_ROOT_EMAIL`
- `LOCAL_GITLAB_ROOT_PASSWORD`

## 로컬 GitLab에 bot 붙이기

Merge Request가 만들어진 뒤에는 아래 스크립트로 로컬 GitLab과 `review-bot`을 연결할 수 있다.

```bash
python3 /home/et16/work/review_system/ops/scripts/attach_local_gitlab_bot.py
```

이 스크립트는 아래를 자동으로 수행한다.

1. root personal access token 재발급
2. `ops/.env`를 GitLab adapter 기준으로 갱신
3. `review-bot-api`, `review-bot-worker` 재빌드 및 재기동
4. 로컬 네트워크 webhook 허용 설정
5. 기존 bot 댓글 정리 및 bot 상태 초기화
6. `root/altidev4` 프로젝트에 Note webhook 등록
7. 선택적으로 현재 MR에 `@review-bot` comment를 남겨 초기 리뷰 요청

기본값은 아래 MR을 대상으로 한다.

- 프로젝트: `root/altidev4`
- MR iid: `1`

실행 후 봇 댓글은 아래 Merge Request 화면에서 바로 확인한다.

- `http://127.0.0.1:18929/root/altidev4/-/merge_requests/1`

현재 운영 기준의 재리뷰는 push 자동 트리거가 아니라,
MR comment에 `@review-bot` mention이 들어왔을 때만 반응한다.

## clean replay reset/reseed

검증 중에 MR 상태나 bot discussion 이력이 섞였을 때는 아래 스크립트로
baseline MR과 bot 상태를 다시 고정할 수 있다.

```bash
python3 /home/et16/work/review_system/ops/scripts/replay_local_gitlab_tde_review.py
```

이 스크립트는 기본적으로 아래를 수행한다.

1. 로컬 GitLab 준비 확인
2. `root/altidev4-review` 프로젝트 확보
3. `tde_base`를 고정 ref로 force-push
4. `tde_first`를 baseline ref로 force-push
5. 기존 open MR 삭제 후 새 MR 생성
6. bot 재부착 및 초기 `@review-bot` mention 요청

내장된 baseline ref:

- `tde_base`: `b5425ede8aabd45aa9edc09e7b33617aae66ce4c`
- `tde_first`: `305df15e75a4c6430c075f84877e93955eb32749`

fixture 의미:

- `tde_base`
  - 리뷰 기준선 역할을 하는 target snapshot
- `tde_first`
  - 초기 inline thread가 생성되어야 하는 baseline source snapshot

## default incremental replay

기본 검증용 incremental sequence까지 한 번에 재생하려면:

```bash
python3 /home/et16/work/review_system/ops/scripts/replay_local_gitlab_tde_review.py \
  --replay-default-updates
```

내장된 update ref 순서:

1. `2d144f954952d5556eb2d99ba1b1d8fcc01c6d78`
2. `d75b6b8fe7d03ecd47bb46e8c4af596d9a14ed76`
3. `d6665020440e83624e01af839f4f43dcb646a580`

이 시퀀스는 각 update 뒤에 `@review-bot` mention 요청을 보내고,
incremental-equivalent smoke 흐름 대신 manual full review / stale resolve / untouched thread 보호 같은
현재 bot 동작을 반복 검증할 때 사용한다.

update ref 의미:

1. 첫 update
   - incremental review가 baseline thread를 중복 생성하지 않는지 확인
2. 두 번째 update
   - touched scope가 바뀌어도 unrelated thread가 유지되는지 확인
3. 세 번째 update
   - feedback/sync 이후 stale resolve와 open thread count 변화를 확인

## 표준 smoke 검증

baseline 재생성, default incremental replay, human reply, resolve, sync까지 한 번에
검증하고 싶으면 아래 wrapper를 사용한다.

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_tde_review.sh
```

이 명령은 내부적으로 아래를 고정 실행한다.

- `--replay-default-updates`
- `--reply-first-open-thread`
- `--resolve-first-open-thread`
- `--trigger-sync-after-thread-actions`
- `--assert-default-smoke`

추가로 JSON artifact를 남기고 싶으면:

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_tde_review.sh \
  --json-output /tmp/review-bot-smoke.json
```

`--assert-default-smoke`는 아래 invariant를 자동 검증한다.

- baseline review가 `success`로 끝나는지
- baseline에서 최소 1개 이상의 open thread가 생기는지
- 각 incremental replay가 해당 head SHA에서 `success`로 끝나는지
- failed publication이 없는지
- reply/resolve 후 sync에서 feedback count가 증가하는지
- resolve 후 sync에서 open thread count가 감소하는지

권장 운영 위치:

- 기본 PR CI가 아니라, 수동 smoke 또는 pre-release smoke로 사용한다.
- 이유는 local GitLab bootstrap과 bot rebuild 비용이 크기 때문이다.

## 실제로 수행되는 일

스크립트는 아래 순서로 동작한다.

1. `altidev4` 저장소에서 `tde_first`, `tde_base` 브랜치 존재 확인
2. GitLab 프로젝트 조회 또는 생성
3. local git remote `gitlab` 추가 또는 갱신
4. `tde_base`, `tde_first` 브랜치를 GitLab으로 push
5. 기존 open MR 존재 여부 확인
6. 없으면 `tde_first -> tde_base` Merge Request 생성

## 보조 옵션

초안 MR로 올리고 싶으면:

```bash
bash /home/et16/work/review_system/ops/scripts/create_altidev4_tde_review.sh --draft
```

SSH 대신 HTTP remote를 쓰고 싶으면:

```bash
bash /home/et16/work/review_system/ops/scripts/create_altidev4_tde_review.sh --remote-kind http
```

## 참고

실제 GitLab URL과 token이 아직 없으면, 현재는 dry-run까지만 수행 가능하다.
그 상태에서도 MR 제목/설명/브랜치 조합과 push 순서는 이미 검증된다.
