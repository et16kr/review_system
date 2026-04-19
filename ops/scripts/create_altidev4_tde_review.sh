#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

exec python3 "$ROOT_DIR/ops/scripts/create_gitlab_merge_request.py" \
  --repo-path /home/et16/work/altidev4 \
  --source-branch tde_first \
  --target-branch tde_base \
  --project-name altidev4 \
  --project-path altidev4 \
  --title "TDE review: tde_first -> tde_base" \
  "$@"
