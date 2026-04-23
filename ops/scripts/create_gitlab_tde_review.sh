#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

exec python3 "$ROOT_DIR/ops/scripts/create_gitlab_merge_request.py" \
  --repo-path "${LOCAL_GITLAB_SMOKE_REPO_PATH:-/home/et16/work/review-system-smoke}" \
  --source-branch tde_first \
  --target-branch tde_base \
  --project-name review-system-smoke \
  --project-path review-system-smoke \
  --title "TDE review: tde_first -> tde_base" \
  "$@"
