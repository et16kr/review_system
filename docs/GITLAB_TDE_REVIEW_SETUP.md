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
6. `root/altidev4` 프로젝트에 Merge Request webhook 등록
7. 현재 MR에 초기 리뷰 1회 실행

기본값은 아래 MR을 대상으로 한다.

- 프로젝트: `root/altidev4`
- MR iid: `1`

실행 후 봇 댓글은 아래 Merge Request 화면에서 바로 확인한다.

- `http://127.0.0.1:18929/root/altidev4/-/merge_requests/1`

자동 재리뷰는 GitLab Merge Request `update` 이벤트 중에서도
실제 새 커밋이 들어온 경우에만 반응하도록 맞춰 둔다.

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
