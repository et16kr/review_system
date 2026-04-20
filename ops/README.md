# Ops

이 디렉터리는 workspace 분리 후 통합 실행 자산을 둡니다.

현재 포함 항목:

- `docker-compose.yml`
- `.env.example`
- `scripts/create_gitlab_merge_request.py`
- `scripts/create_altidev4_tde_review.sh`
- `scripts/bootstrap_local_gitlab_tde_review.py`
- `scripts/attach_local_gitlab_bot.py`
- `scripts/replay_local_gitlab_tde_review.py`
- `scripts/smoke_local_gitlab_tde_review.sh`
- `review-bot-policy.example.json`

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

로컬 GitLab MR에 bot까지 붙이려면:

```bash
python3 /home/et16/work/review_system/ops/scripts/attach_local_gitlab_bot.py
```

로컬 GitLab MR과 bot 상태를 clean replay 가능한 baseline으로 다시 맞추려면:

```bash
python3 /home/et16/work/review_system/ops/scripts/replay_local_gitlab_tde_review.py
```

표준 smoke 시나리오를 한 번에 재생하고, 실패 시 non-zero exit code를 받으려면:

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_tde_review.sh
```
