#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/et16/work/review_system"
SCRIPT="$ROOT/ops/scripts/smoke_local_gitlab_lifecycle_review.sh"

bash "$SCRIPT" "$@"
