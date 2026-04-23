# Ops

이 디렉터리는 workspace 분리 후 통합 실행 자산을 둡니다.

현재 포함 항목:

- `docker-compose.yml`
- `.env.example`
- `scripts/create_gitlab_merge_request.py`
- `scripts/create_gitlab_tde_review.sh`
- `scripts/bootstrap_local_gitlab_tde_review.py`
- `scripts/attach_local_gitlab_bot.py`
- `scripts/replay_local_gitlab_tde_review.py`
- `scripts/smoke_local_gitlab_tde_review.sh`
- `scripts/smoke_local_gitlab_lifecycle_review.sh`
- `scripts/smoke_local_gitlab_multilang_review.sh`
- `scripts/capture_review_bot_baseline.py`
- `scripts/capture_wrong_language_telemetry.py`
- `scripts/build_wrong_language_backlog.py`
- `fixtures/review_smoke/`
- `review-bot-policy.example.json`

초기 실행:

```bash
cd ops
docker compose up --build
```

GitLab에 실제 Merge Request를 먼저 만들 때:

```bash
bash /home/et16/work/review_system/ops/scripts/create_gitlab_tde_review.sh --dry-run
```

상세 절차와 표준 smoke 흐름은 [OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:1)에 정리했다.

로컬 GitLab 인스턴스를 함께 띄워서 smoke MR까지 자동 생성하려면:

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
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_lifecycle_review.sh
```

기존 `smoke_local_gitlab_tde_review.sh`는 compatibility wrapper로 계속 사용할 수 있습니다.

Phase A baseline snapshot을 남기려면:

```bash
python3 /home/et16/work/review_system/ops/scripts/capture_review_bot_baseline.py \
  --baseline-kind v0
```

wrong-language telemetry snapshot만 따로 남기려면:

```bash
python3 /home/et16/work/review_system/ops/scripts/capture_wrong_language_telemetry.py \
  --window 28d
```

wrong-language detector backlog를 바로 Markdown으로 만들려면:

```bash
python3 /home/et16/work/review_system/ops/scripts/build_wrong_language_backlog.py \
  --window 28d
```

mixed-language smoke를 돌리려면:

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture synthetic-mixed-language \
  --json-output /tmp/review-bot-multilang-smoke.json
```

이 smoke는 `markdown + yaml + sql + framework file` 조합에서 language tag와 wrong-language telemetry 흐름까지 함께 검증합니다.

CUDA targeted fixture를 별도 project ref로 돌리려면:

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture cuda-targeted \
  --project-ref root/review-system-cuda-smoke \
  --json-output /tmp/review-bot-cuda-smoke.json
```

curated polyglot fixture를 돌리려면:

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture curated-polyglot \
  --project-ref root/review-system-curated-polyglot-smoke \
  --json-output /tmp/review-bot-curated-polyglot-smoke.json
```
