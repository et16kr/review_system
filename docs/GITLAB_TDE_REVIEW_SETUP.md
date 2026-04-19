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
