# GitLab TDE 리뷰 준비

## 목적

이 문서는 local smoke 저장소의 `tde_first -> tde_base` 변경을 GitLab Merge Request로 만들고,
이후 `review-bot`까지 연결하는 표준 절차를 정리합니다.

기본 local GitLab smoke 프로젝트명은 `review-system-smoke`,
기본 project ref는 `root/review-system-smoke`입니다.

## 준비 변수

local seed 저장소 경로는 아래 env로 지정합니다.

```bash
export LOCAL_GITLAB_SMOKE_REPO_PATH=/absolute/path/to/review-system-smoke
```

로컬 GitLab이 아닌 외부 GitLab에 MR을 만들 때는 아래 값이 필요합니다.

```bash
export GITLAB_URL=https://gitlab.example.com
export GITLAB_TOKEN=...
export GITLAB_NAMESPACE_PATH=group-or-user
export GITLAB_PROJECT_REF=group-or-user/review-system-smoke
```

## Dry Run

```bash
bash /home/et16/work/review_system/ops/scripts/create_gitlab_tde_review.sh --dry-run
```

이 명령은 source/target branch, MR title, description 초안, diff summary를 출력합니다.

## 실제 GitLab MR 생성

기존 프로젝트가 이미 있을 때:

```bash
export GITLAB_URL=https://gitlab.example.com
export GITLAB_TOKEN=...
export GITLAB_PROJECT_REF=group-or-user/review-system-smoke

bash /home/et16/work/review_system/ops/scripts/create_gitlab_tde_review.sh
```

새 프로젝트를 만들면서 진행할 때:

```bash
export GITLAB_URL=https://gitlab.example.com
export GITLAB_TOKEN=...
export GITLAB_NAMESPACE_PATH=group-or-user

bash /home/et16/work/review_system/ops/scripts/create_gitlab_tde_review.sh --create-project
```

## 로컬 GitLab 부트스트랩

```bash
python3 /home/et16/work/review_system/ops/scripts/bootstrap_local_gitlab_tde_review.py
```

이 스크립트는 아래를 자동으로 수행합니다.

1. 로컬 GitLab 컨테이너 실행
2. root 관리자 계정 보장
3. root personal access token 생성
4. `root/review-system-smoke` 프로젝트 생성
5. `tde_base`, `tde_first` 브랜치 push
6. `tde_first -> tde_base` Merge Request 생성

기본 접속 정보:

- GitLab URL: `http://127.0.0.1:18929`
- 프로젝트: `http://127.0.0.1:18929/root/review-system-smoke`
- MR: `http://127.0.0.1:18929/root/review-system-smoke/-/merge_requests/1`

## 로컬 GitLab에 bot 붙이기

```bash
python3 /home/et16/work/review_system/ops/scripts/attach_local_gitlab_bot.py
```

이 스크립트는 아래를 자동으로 수행합니다.

1. root personal access token 재발급
2. `ops/.env`를 GitLab adapter 기준으로 갱신
3. `review-bot-api`, `review-bot-worker` 재빌드 및 재기동
4. 로컬 네트워크 webhook 허용 설정
5. 기존 bot 댓글 정리 및 bot 상태 초기화
6. `root/review-system-smoke` 프로젝트에 Note webhook 등록
7. 선택적으로 현재 MR에 `@review-bot` comment를 남겨 초기 리뷰 요청

기본 대상:

- 프로젝트: `root/review-system-smoke`
- MR iid: `1`

## clean replay reset/reseed

```bash
python3 /home/et16/work/review_system/ops/scripts/replay_local_gitlab_tde_review.py
```

이 스크립트는 기본적으로 아래를 수행합니다.

1. 로컬 GitLab 준비 확인
2. `root/review-system-smoke` 프로젝트 확보
3. `tde_base`를 고정 ref로 force-push
4. `tde_first`를 baseline ref로 force-push
5. 기존 open MR 삭제 후 새 MR 생성
6. bot 재부착 및 초기 `@review-bot` mention 요청

## 표준 smoke 검증

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_tde_review.sh
```

이 wrapper는 baseline reset/reseed, default incremental replay, human reply, resolve, `/sync`, smoke invariant 검증을 한 번에 수행합니다.

mixed-language smoke:

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.sh
```
