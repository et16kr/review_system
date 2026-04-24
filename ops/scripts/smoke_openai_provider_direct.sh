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

Environment overrides:
- REVIEW_SYSTEM_ROOT: repository root. Default resolves from this script path.
- REVIEW_SYSTEM_ENV_FILE: env file to load. Default: $REVIEW_SYSTEM_ROOT/ops/.env
- BOT_OPENAI_BASE_URL: OpenAI-compatible base URL. Default: https://api.openai.com/v1
- BOT_OPENAI_MODEL_OVERRIDE: model override if --model is not provided.
EOF
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

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY is not set." >&2
  exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

curl -sS "$BASE_URL/models" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -o "$tmpdir/models.json"

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
  curl -sS "$BASE_URL/responses" \
    -H "Authorization: Bearer sk-invalid-test" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$MODEL\",\"input\":\"ping\",\"max_output_tokens\":16}" \
    -o "$tmpdir/invalid.json"

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

curl -sS "$BASE_URL/responses" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"input\":\"ping\",\"max_output_tokens\":16}" \
  -o "$tmpdir/live.json"

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
