# Ops

이 디렉터리는 workspace 분리 후 통합 실행 자산을 둡니다.

현재 포함 항목:

- `docker-compose.yml`
- `.env.example`
- `scripts/create_gitlab_merge_request.py`
- `scripts/create_altidev4_tde_review.sh`

초기 실행:

```bash
cd ops
docker compose up --build
```

GitLab에 실제 Merge Request를 먼저 만들 때:

```bash
bash /home/et16/work/review_system/ops/scripts/create_altidev4_tde_review.sh --dry-run
```

상세 절차는 [GITLAB_TDE_REVIEW_SETUP.md](/home/et16/work/review_system/docs/GITLAB_TDE_REVIEW_SETUP.md:1)에 정리했다.

로컬 GitLab 인스턴스를 함께 띄워서 `altidev4` MR까지 자동 생성하려면:

```bash
python3 /home/et16/work/review_system/ops/scripts/bootstrap_local_gitlab_tde_review.py
```
