#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/et16/work/review_system"
SCRIPT="$ROOT/ops/scripts/replay_local_gitlab_lifecycle_review.py"

python3 "$SCRIPT" \
  --replay-default-updates \
  --reply-first-open-thread \
  --resolve-first-open-thread \
  --trigger-sync-after-thread-actions \
  --assert-default-smoke \
  "$@"
