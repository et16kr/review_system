# Review Smoke Fixtures

이 디렉터리는 local GitLab smoke와 engine-only fixture contract 테스트가 함께 쓰는
repo-local fixture를 둔다.

원칙:

- smoke 실행 중 외부 저장소를 clone/fetch하지 않는다.
- 각 fixture는 `base/`, `feature/`, `expected_smoke.json`, `manifest.yaml`을 가진다.
- `base/`와 `feature/`는 GitLab MR의 target/source branch를 재현한다.
- `expected_smoke.json`은 daily smoke에서 검증할 최소 contract만 담는다.
- `density_contract`는 local GitLab smoke의 first batch가 너무 커지거나 한 파일에 몰리는
  회귀를 잡기 위한 comment 수/path 분산 기준이다.
- 외부-derived fixture를 추가할 때는 `external_sources.yaml`에 source repo, pinned ref,
  license, imported path, transformation을 먼저 남긴다.

현재 fixture:

- `synthetic-mixed-language`: 기존 mixed-language smoke의 기본 profile.
- `curated-polyglot`: Go service, Dockerfile, Kubernetes YAML 조합 targeted profile.
- `cuda-targeted`: CUDA language/profile routing을 함께 보는 targeted profile.

실행 예:

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture synthetic-mixed-language \
  --json-output /tmp/review-bot-multilang-smoke.json
```

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture cuda-targeted \
  --project-ref root/review-system-cuda-smoke \
  --json-output /tmp/review-bot-cuda-smoke.json
```

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture curated-polyglot \
  --project-ref root/review-system-curated-polyglot-smoke \
  --json-output /tmp/review-bot-curated-polyglot-smoke.json
```
