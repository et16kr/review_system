#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
DEFAULT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
ROOT_SOURCE="script_dir"
ENV_FILE_SOURCE="ops_default"
ROOT="${REVIEW_SYSTEM_ROOT:-$DEFAULT_ROOT}"
if [[ -n "${REVIEW_SYSTEM_ROOT:-}" ]]; then
  ROOT_SOURCE="env"
fi
ENV_FILE="${REVIEW_SYSTEM_ENV_FILE:-$ROOT/ops/.env}"
if [[ -n "${REVIEW_SYSTEM_ENV_FILE:-}" ]]; then
  ENV_FILE_SOURCE="env"
fi
MODEL_OVERRIDE="${BOT_OPENAI_MODEL_OVERRIDE:-}"
DEFAULT_OPENAI_BASE_URL="https://api.openai.com/v1"
EXPECT_LIVE_OPENAI=0
OPENAI_DIRECT_SMOKE_CONNECT_TIMEOUT_SECONDS="${OPENAI_DIRECT_SMOKE_CONNECT_TIMEOUT_SECONDS:-5}"
OPENAI_DIRECT_SMOKE_MAX_TIME_SECONDS="${OPENAI_DIRECT_SMOKE_MAX_TIME_SECONDS:-30}"

usage() {
  cat <<'EOF'
Usage: ops/scripts/smoke_openai_provider_direct.sh [--expect-live-openai] [--model MODEL]

Directly probes the configured OpenAI-compatible Responses endpoint without review-bot fallback so tests can distinguish:
- network/auth path is reachable
- default OpenAI endpoint still rejects an invalid API key with 401 invalid_api_key
- configured key either succeeds live or fails with a concrete direct-provider error

Exit codes:
- 0: probe completed; live OpenAI may still be unavailable if summary says insufficient_quota
- 1: usage or assertion failure
- 2: live OpenAI was required but direct provider call did not succeed
- curl exit status: direct probe transport failure, for example 28 on timeout

Environment overrides:
- REVIEW_SYSTEM_ROOT: repository root. Default resolves from this script path.
- REVIEW_SYSTEM_ENV_FILE: env file to load. Default: $REVIEW_SYSTEM_ROOT/ops/.env
- BOT_OPENAI_BASE_URL: OpenAI-compatible base URL. Default: https://api.openai.com/v1
- BOT_OPENAI_MODEL_OVERRIDE: model override if --model is not provided.
- OPENAI_DIRECT_SMOKE_CONNECT_TIMEOUT_SECONDS: curl connect timeout. Default: 5
- OPENAI_DIRECT_SMOKE_MAX_TIME_SECONDS: curl overall timeout per probe. Default: 30
EOF
}

run_curl_probe() {
  local probe_name="$1"
  local url="$2"
  local output_path="$3"
  shift 3

  local exit_code=0
  if curl -sS \
    --connect-timeout "$OPENAI_DIRECT_SMOKE_CONNECT_TIMEOUT_SECONDS" \
    --max-time "$OPENAI_DIRECT_SMOKE_MAX_TIME_SECONDS" \
    "$url" \
    "$@" \
    -o "$output_path"; then
    return 0
  else
    exit_code=$?
  fi
  printf '%s\n' "${probe_name}_curl_exit=$exit_code"
  return "$exit_code"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --expect-live-openai)
      EXPECT_LIVE_OPENAI=1
      shift
      ;;
    --model)
      MODEL_OVERRIDE="${2:?missing value for --model}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "${line#\#}" != "$line" ]] && continue
  [[ "$line" != *=* ]] && continue
  key="${line%%=*}"
  value="${line#*=}"
  export "$key=$value"
done <"$ENV_FILE"

MODEL="${MODEL_OVERRIDE:-${BOT_OPENAI_MODEL:-gpt-5.2}}"
BASE_URL_RAW="${BOT_OPENAI_BASE_URL:-$DEFAULT_OPENAI_BASE_URL}"
BASE_URL="${BASE_URL_RAW%/}"

printf '%s\n' "repo_root=$ROOT"
printf '%s\n' "repo_root_source=$ROOT_SOURCE"
printf '%s\n' "env_file=$ENV_FILE"
printf '%s\n' "env_file_source=$ENV_FILE_SOURCE"
printf '%s\n' "endpoint_base_url=$BASE_URL"
printf '%s\n' "curl_connect_timeout_seconds=$OPENAI_DIRECT_SMOKE_CONNECT_TIMEOUT_SECONDS"
printf '%s\n' "curl_max_time_seconds=$OPENAI_DIRECT_SMOKE_MAX_TIME_SECONDS"

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY is not set." >&2
  exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

run_curl_probe "models_probe" "$BASE_URL/models" "$tmpdir/models.json" \
  -H "Authorization: Bearer $OPENAI_API_KEY"

python3 - "$tmpdir/models.json" <<'PY'
import json
import sys

payload = json.loads(open(sys.argv[1], encoding="utf-8").read())
if "error" in payload:
    err = payload["error"]
    print("models_probe_status=error")
    print(f"models_probe_type={err.get('type')}")
    print(f"models_probe_code={err.get('code')}")
    print(f"models_probe_message={err.get('message')}")
    raise SystemExit(1)
print("models_probe_status=ok")
PY

if [[ "$BASE_URL" == "$DEFAULT_OPENAI_BASE_URL" ]]; then
  run_curl_probe "invalid_key_probe" "$BASE_URL/responses" "$tmpdir/invalid.json" \
    -H "Authorization: Bearer sk-invalid-test" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$MODEL\",\"input\":\"ping\",\"max_output_tokens\":16}"

  python3 - "$tmpdir/invalid.json" <<'PY'
import json
import sys

payload = json.loads(open(sys.argv[1], encoding="utf-8").read())
error = payload.get("error") or {}
if error.get("code") != "invalid_api_key":
    print("invalid_key_probe_status=unexpected")
    print(f"invalid_key_probe_payload={json.dumps(payload, ensure_ascii=False)}")
    raise SystemExit(1)
print("invalid_key_probe_status=ok")
print(f"invalid_key_probe_type={error.get('type')}")
print(f"invalid_key_probe_code={error.get('code')}")
PY
else
  printf '%s\n' "invalid_key_probe_status=skipped_non_default_base_url"
fi

run_curl_probe "live_probe" "$BASE_URL/responses" "$tmpdir/live.json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"input\":\"ping\",\"max_output_tokens\":16}"

live_status="$(
  python3 - "$tmpdir/live.json" <<'PY'
import json
import sys

payload = json.loads(open(sys.argv[1], encoding="utf-8").read())
if "error" in payload:
    error = payload["error"]
    print("error")
    print(f"live_probe_type={error.get('type')}")
    print(f"live_probe_code={error.get('code')}")
    print(f"live_probe_message={error.get('message')}")
else:
    text = ""
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                text += content.get("text", "")
    print("ok")
    print(f"live_probe_model={payload.get('model')}")
    print(f"live_probe_text={text[:120]}")
PY
)"

printf '%s\n' "configured_model=$MODEL"
printf '%s\n' "$live_status"

if [[ "$EXPECT_LIVE_OPENAI" -eq 1 && "$live_status" != ok* ]]; then
  exit 2
fi
