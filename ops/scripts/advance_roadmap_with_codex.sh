#!/usr/bin/env bash
set -euo pipefail

ROOT="${REVIEW_SYSTEM_ROOT:-/home/et16/work/review_system}"
ROADMAP_FILE="${ROADMAP_FILE:-docs/ROADMAP.md}"
MAX_ITERS="${MAX_ITERS:-1}"
MAX_BLOCKED_SKIPS="${MAX_BLOCKED_SKIPS:-10}"
SANDBOX="${CODEX_SANDBOX:-workspace-write}"
MODEL="${CODEX_MODEL:-}"
COMMIT_PREFIX="${COMMIT_PREFIX:-Advance roadmap item}"
OPENAI_DIRECT_SMOKE="${OPENAI_DIRECT_SMOKE:-0}"
UNTIL_DONE=0
NO_COMMIT=0

usage() {
  cat <<'EOF'
Usage: ops/scripts/advance_roadmap_with_codex.sh [options]

Run Codex in one-commit roadmap advancement loops.

Options:
  --roadmap-file PATH
                     Roadmap document to advance, relative to repo root or absolute path.
                     Default: ROADMAP_FILE or docs/ROADMAP.md.
  --max-iters N      Maximum completed roadmap units (usually commits) to create.
                     Default: MAX_ITERS or 1.
  --max-blocked-skips N
                     Maximum blocked roadmap units to skip in one run. Default: MAX_BLOCKED_SKIPS or 10.
  --model NAME       Pass a model to codex exec. Default: CODEX_MODEL or Codex default.
  --sandbox MODE     Sandbox for codex exec. Default: CODEX_SANDBOX or workspace-write.
  --until-done       Continue until Codex reports ROADMAP_COMPLETE.
  --enable-openai-direct-smoke
                     Run provider-direct smoke preflight before each iteration.
  --skip-openai-direct-smoke
                     Explicitly disable provider-direct smoke preflight.
  --no-commit        Leave changes uncommitted after one completed iteration.
  -h, --help         Show this help.

Environment:
  REVIEW_SYSTEM_ROOT Repository root. Default: /home/et16/work/review_system.
  ROADMAP_FILE       Same as --roadmap-file.
  MAX_ITERS          Same as --max-iters.
  MAX_BLOCKED_SKIPS  Same as --max-blocked-skips.
  CODEX_MODEL        Same as --model.
  CODEX_SANDBOX      Same as --sandbox.
  OPENAI_DIRECT_SMOKE
                     Set to 1 to enable provider-direct smoke preflight.
  COMMIT_PREFIX      Commit message fallback prefix.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --roadmap-file)
      ROADMAP_FILE="${2:?missing value for --roadmap-file}"
      shift 2
      ;;
    --max-iters)
      MAX_ITERS="${2:?missing value for --max-iters}"
      shift 2
      ;;
    --max-blocked-skips)
      MAX_BLOCKED_SKIPS="${2:?missing value for --max-blocked-skips}"
      shift 2
      ;;
    --model)
      MODEL="${2:?missing value for --model}"
      shift 2
      ;;
    --sandbox)
      SANDBOX="${2:?missing value for --sandbox}"
      shift 2
      ;;
    --until-done)
      UNTIL_DONE=1
      shift
      ;;
    --enable-openai-direct-smoke)
      OPENAI_DIRECT_SMOKE=1
      shift
      ;;
    --skip-openai-direct-smoke)
      OPENAI_DIRECT_SMOKE=0
      shift
      ;;
    --no-commit)
      NO_COMMIT=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! [[ "$MAX_ITERS" =~ ^[1-9][0-9]*$ ]]; then
  echo "MAX_ITERS must be a positive integer: $MAX_ITERS" >&2
  exit 2
fi

if ! [[ "$MAX_BLOCKED_SKIPS" =~ ^[0-9]+$ ]]; then
  echo "MAX_BLOCKED_SKIPS must be a non-negative integer: $MAX_BLOCKED_SKIPS" >&2
  exit 2
fi

if ! [[ "$UNTIL_DONE" =~ ^[01]$ ]]; then
  echo "UNTIL_DONE must be 0 or 1: $UNTIL_DONE" >&2
  exit 2
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "codex CLI is not available on PATH." >&2
  exit 127
fi

cd "$ROOT"

if [[ "$(git rev-parse --show-toplevel)" != "$ROOT" ]]; then
  echo "Repository root mismatch. Expected $ROOT" >&2
  exit 2
fi

if [[ "$ROADMAP_FILE" = /* ]]; then
  roadmap_rel="$(realpath --relative-to="$ROOT" "$ROADMAP_FILE")"
else
  roadmap_rel="$ROADMAP_FILE"
fi

if [[ "$roadmap_rel" == ..* ]]; then
  echo "ROADMAP_FILE must resolve inside the repository: $ROADMAP_FILE" >&2
  exit 2
fi

roadmap_abs="$ROOT/$roadmap_rel"
if [[ ! -f "$roadmap_abs" ]]; then
  echo "Roadmap file not found: $roadmap_abs" >&2
  exit 2
fi

require_clean_tree() {
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "Working tree is not clean. Stop before starting the next roadmap iteration." >&2
    git status --short >&2
    exit 1
  fi
}

has_changes() {
  [[ -n "$(git status --porcelain)" ]]
}

parse_status() {
  local file="$1"
  grep -E '^STATUS: (COMPLETED|BLOCKED|ROADMAP_COMPLETE)$' "$file" | tail -n 1 | sed 's/^STATUS: //'
}

parse_commit_message() {
  local file="$1"
  local message
  message="$(grep -E '^COMMIT_MESSAGE: .+' "$file" | tail -n 1 | sed 's/^COMMIT_MESSAGE: //')"
  if [[ -n "$message" ]]; then
    printf '%s\n' "$message"
  else
    printf '%s\n' "$COMMIT_PREFIX"
  fi
}

normalize_single_line() {
  printf '%s' "$1" | tr '\n' ' ' | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//'
}

extract_structured_field() {
  local file="$1"
  local field="$2"
  local line
  line="$(grep -E "^${field}: " "$file" | tail -n 1 || true)"
  line="${line#"$field: "}"
  normalize_single_line "$line"
}

extract_blocked_unit() {
  local file="$1"
  local unit
  unit="$(extract_structured_field "$file" "BLOCKED_UNIT")"
  if [[ -n "$unit" ]]; then
    printf '%s\n' "$unit"
    return 0
  fi
  awk '
    /^Validation run and result:/ { exit }
    /^STATUS: / { exit }
    /^COMMIT_MESSAGE: / { exit }
    /^BLOCKED_UNIT: / { next }
    /^BLOCKER_TYPE: / { next }
    /^BLOCKED_REASON: / { next }
    /^[[:space:]]*$/ { next }
    { print; exit }
  ' "$file"
}

extract_blocked_reason() {
  local file="$1"
  local reason
  reason="$(extract_structured_field "$file" "BLOCKED_REASON")"
  if [[ -n "$reason" ]]; then
    printf '%s\n' "$reason"
    return 0
  fi
  awk '
    /^Validation run and result:/ { exit }
    /^STATUS: / { exit }
    /^COMMIT_MESSAGE: / { exit }
    /^BLOCKED_UNIT: / { next }
    /^BLOCKER_TYPE: / { next }
    /^BLOCKED_REASON: / { next }
    /^[[:space:]]*$/ { next }
    { lines[++count] = $0 }
    END {
      for (i = 1; i <= count; i++) {
        printf "%s%s", lines[i], (i < count ? " " : ORS)
      }
    }
  ' "$file"
}

extract_validation_summary() {
  local file="$1"
  awk '
    /^Validation run and result:/ { capture = 1; next }
    capture && /^STATUS: / { exit }
    capture && /^COMMIT_MESSAGE: / { exit }
    capture && /^[[:space:]]*$/ { next }
    capture {
      line = $0
      sub(/^[[:space:]]*-[[:space:]]*/, "", line)
      gsub(/`/, "", line)
      lines[++count] = line
    }
    END {
      for (i = 1; i <= count; i++) {
        printf "%s%s", lines[i], (i < count ? " | " : ORS)
      }
    }
  ' "$file"
}

append_blocked_summary() {
  local output_file="$1"
  local blocked_file="$2"
  {
    printf '%s\n' '--- blocked unit ---'
    sed -n '1,220p' "$output_file"
    printf '\n'
  } >>"$blocked_file"
}

record_blocked_artifact_entry() {
  local output_file="$1"
  local attempt="$2"
  local date_utc
  local pending_file
  local blocked_unit
  local blocker_type
  local blocked_reason
  local validation_summary
  local status_line

  date_utc="$(date -u +%F)"
  pending_file="$tmpdir/blocked-artifact-$date_utc.md"
  blocked_unit="$(normalize_single_line "$(extract_blocked_unit "$output_file")")"
  blocker_type="$(extract_structured_field "$output_file" "BLOCKER_TYPE")"
  blocked_reason="$(normalize_single_line "$(extract_blocked_reason "$output_file")")"
  validation_summary="$(normalize_single_line "$(extract_validation_summary "$output_file")")"
  status_line="$(grep -E '^STATUS: (COMPLETED|BLOCKED|ROADMAP_COMPLETE)$' "$output_file" | tail -n 1 || true)"

  if [[ -z "$blocked_unit" ]]; then
    blocked_unit="blocked roadmap unit"
  fi
  if [[ -z "$blocked_reason" ]]; then
    blocked_reason="See Codex output for blocker details."
  fi

  {
    printf '## Attempt %s\n' "$attempt"
    printf -- '- date: %s\n' "$date_utc"
    printf -- '- attempt: %s\n' "$attempt"
    printf -- '- blocked_unit: %s\n' "$blocked_unit"
    printf -- '- reason: %s\n' "$blocked_reason"
    if [[ -n "$blocker_type" ]]; then
      printf -- '- blocker_type: %s\n' "$blocker_type"
    fi
    if [[ -n "$validation_summary" ]]; then
      printf -- '- validation_summary: %s\n' "$validation_summary"
    fi
    if [[ -n "$status_line" ]]; then
      printf -- '- status: %s\n' "$status_line"
    fi
    printf '\n'
  } >>"$pending_file"
}

flush_blocked_artifact_entries() {
  local pending_files=()
  local pending_file
  local file_name
  local date_utc
  local artifact_dir
  local artifact_file

  shopt -s nullglob
  pending_files=("$tmpdir"/blocked-artifact-*.md)
  shopt -u nullglob

  if [[ "${#pending_files[@]}" -eq 0 ]]; then
    return 0
  fi

  artifact_dir="$ROOT/docs/baselines/roadmap_automation"
  mkdir -p "$artifact_dir"

  for pending_file in "${pending_files[@]}"; do
    file_name="$(basename "$pending_file")"
    date_utc="${file_name#blocked-artifact-}"
    date_utc="${date_utc%.md}"
    artifact_file="$artifact_dir/blocked_roadmap_units_${date_utc}.md"
    if [[ ! -e "$artifact_file" ]]; then
      printf '# Blocked Roadmap Units - %s\n\n' "$date_utc" >"$artifact_file"
    elif [[ -s "$artifact_file" ]]; then
      printf '\n' >>"$artifact_file"
    fi
    cat "$pending_file" >>"$artifact_file"
    rm -f "$pending_file"
  done
}

collect_openai_direct_smoke() {
  local output_file="$1"
  local smoke_script="$ROOT/ops/scripts/smoke_openai_provider_direct.sh"
  if [[ "$OPENAI_DIRECT_SMOKE" == "0" ]]; then
    printf '%s\n' "OpenAI direct smoke preflight: skipped by configuration." >"$output_file"
    return 0
  fi
  if [[ ! -x "$smoke_script" ]]; then
    printf '%s\n' "OpenAI direct smoke preflight: unavailable (missing executable $smoke_script)." >"$output_file"
    return 0
  fi
  if "$smoke_script" >"$output_file" 2>&1; then
    return 0
  fi
  local exit_code=$?
  printf '\n%s\n' "openai_direct_smoke_exit=$exit_code" >>"$output_file"
  return 0
}

tmpdir="$(mktemp -d)"
cleanup() {
  flush_blocked_artifact_entries || true
  rm -rf "$tmpdir"
}
trap cleanup EXIT
blocked_units="$tmpdir/blocked-units.txt"
attempt=0
blocked_skips=0
completed=0

while [[ "$UNTIL_DONE" == "1" || "$completed" -lt "$MAX_ITERS" ]]; do
  attempt=$((attempt + 1))
  require_clean_tree

  prompt="$tmpdir/prompt-$attempt.md"
  output="$tmpdir/output-$attempt.md"
  openai_smoke="$tmpdir/openai-direct-smoke-$attempt.txt"

  collect_openai_direct_smoke "$openai_smoke"

  cat >"$prompt" <<'EOF'
You are advancing __ROADMAP_ABS__.

Follow AGENTS.md and the repository's existing validation guidance.

Perform exactly one smallest executable roadmap unit:
1. Read __ROADMAP_REL__ and pick the next executable item in roadmap order.
1a. If this run already encountered blocked roadmap units, do not pick them again. Move to the next executable item after those blocked units.
2. Before editing, decide whether the item is blocked by missing credentials, external services, human review, local GitLab state, ambiguous product decisions, or unsafe scope.
3. If blocked, do not edit files. Explain the blocker and finish with STATUS: BLOCKED.
4. If executable, create the temporary design note at docs/ROADMAP_AUTOMATION_DESIGN.md.
5. Implement the change.
6. Run the relevant deterministic validation. Use the Validation Baseline section in __ROADMAP_REL__ to choose tests. Do not run long local GitLab smoke unless the roadmap item truly requires it and the environment is ready.
7. Self-review the resulting diff, fix issues you find, then delete docs/ROADMAP_AUTOMATION_DESIGN.md.
8. Update __ROADMAP_REL__ so completed work, remaining work, and any skipped validation are accurate.

Hard constraints:
- Do not run git add, git commit, git reset, git checkout, or git clean.
- Do not touch unrelated files.
- Do not bundle multiple roadmap units.
- Do not leave docs/ROADMAP_AUTOMATION_DESIGN.md in the final diff.
- If tests fail and you cannot fix them within this one unit, leave the diff for inspection and finish with STATUS: BLOCKED.
- If there is no executable roadmap work left, do not edit files and finish with STATUS: ROADMAP_COMPLETE.
- Treat lifecycle smoke and provider-direct smoke as different signals. A lifecycle smoke pass does not prove live OpenAI succeeded when fallback is enabled.
- For provider or lifecycle work, report whether validation used direct OpenAI, stub fallback, or both.

Your final response must include:
- A brief summary.
- If blocked, these lines:
  - BLOCKED_UNIT: <roadmap unit>
  - BLOCKER_TYPE: <missing_credentials|external_services|human_review|local_gitlab_state|ambiguous_product_decision|unsafe_scope|other>
  - BLOCKED_REASON: <brief reason>
- Validation run and result.
- If completed, one line: COMMIT_MESSAGE: <short imperative commit message>
- Final line exactly one of:
STATUS: COMPLETED
STATUS: BLOCKED
STATUS: ROADMAP_COMPLETE
EOF

  perl -0pi -e 's#__ROADMAP_ABS__#'"$roadmap_abs"'#g; s#__ROADMAP_REL__#'"$roadmap_rel"'#g' "$prompt"

  {
    if [[ -s "$blocked_units" ]]; then
      printf '\n[Previously Blocked Units In This Run]\n'
      cat "$blocked_units"
      printf '\n'
    fi
    printf '\n[OpenAI Direct Smoke Preflight]\n'
    cat "$openai_smoke"
    printf '\n'
  } >>"$prompt"

  codex_cmd=(codex exec --full-auto --sandbox "$SANDBOX" -C "$ROOT" -o "$output")
  if [[ -n "$MODEL" ]]; then
    codex_cmd+=(-m "$MODEL")
  fi

  echo "Starting roadmap iteration attempt $attempt (completed $completed/$MAX_ITERS, skipped $blocked_skips/$MAX_BLOCKED_SKIPS)..."
  if ! "${codex_cmd[@]}" <"$prompt"; then
    echo "codex exec failed. Leaving any changes uncommitted for inspection." >&2
    exit 1
  fi

  status="$(parse_status "$output" || true)"
  if [[ -z "$status" ]]; then
    echo "Codex did not emit a recognized STATUS line. Leaving changes uncommitted." >&2
    echo "Last Codex output:" >&2
    sed -n '1,220p' "$output" >&2
    exit 1
  fi

  case "$status" in
    ROADMAP_COMPLETE)
      flush_blocked_artifact_entries
      echo "Roadmap complete according to Codex."
      sed -n '1,220p' "$output"
      exit 0
      ;;
    BLOCKED)
      if has_changes; then
        echo "Roadmap iteration blocked after producing changes. Leaving changes uncommitted for inspection."
        sed -n '1,220p' "$output"
        exit 2
      fi
      blocked_skips=$((blocked_skips + 1))
      append_blocked_summary "$output" "$blocked_units"
      record_blocked_artifact_entry "$output" "$attempt"
      if [[ "$blocked_skips" -gt "$MAX_BLOCKED_SKIPS" ]]; then
        echo "Roadmap iteration blocked and MAX_BLOCKED_SKIPS=$MAX_BLOCKED_SKIPS reached."
        sed -n '1,220p' "$output"
        exit 2
      fi
      echo "Skipping blocked roadmap unit $blocked_skips/$MAX_BLOCKED_SKIPS and continuing."
      sed -n '1,120p' "$output"
      continue
      ;;
    COMPLETED)
      ;;
  esac

  if [[ -e docs/ROADMAP_AUTOMATION_DESIGN.md ]]; then
    echo "Temporary design note still exists. Leaving changes uncommitted." >&2
    exit 1
  fi

  if ! has_changes; then
    echo "Codex reported completion but produced no changes. Stop." >&2
    exit 1
  fi

  if ! git diff --name-only | grep -Fxq "$roadmap_rel"; then
    echo "Codex completed without updating $roadmap_rel. Leaving changes uncommitted." >&2
    exit 1
  fi

  flush_blocked_artifact_entries
  git diff --check

  if [[ "$NO_COMMIT" -eq 1 ]]; then
    echo "--no-commit set. Leaving completed changes uncommitted."
    sed -n '1,220p' "$output"
    exit 0
  fi

  commit_message="$(parse_commit_message "$output")"
  git add -A
  git commit -m "$commit_message"
  completed=$((completed + 1))
  echo "Committed roadmap iteration $completed/$MAX_ITERS: $commit_message"
done

echo "Reached MAX_ITERS=$MAX_ITERS."
