from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ops/scripts/smoke_openai_provider_direct.sh"


def _write_fake_curl(bin_dir: Path) -> None:
    curl_path = bin_dir / "curl"
    curl_path.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail

            output=""
            url=""
            auth=""
            connect_timeout=""
            max_time=""

            while [[ $# -gt 0 ]]; do
              case "$1" in
                --connect-timeout)
                  connect_timeout="${2:?missing curl connect timeout value}"
                  shift 2
                  ;;
                --max-time)
                  max_time="${2:?missing curl max time value}"
                  shift 2
                  ;;
                -o)
                  output="${2:?missing curl output path}"
                  shift 2
                  ;;
                -H)
                  header="${2:?missing curl header value}"
                  case "$header" in
                    "Authorization: Bearer "*)
                      auth="${header#Authorization: Bearer }"
                      ;;
                  esac
                  shift 2
                  ;;
                http*)
                  url="$1"
                  shift
                  ;;
                *)
                  shift
                  ;;
              esac
            done

            if [[ -n "${FAKE_CURL_EXPECT_CONNECT_TIMEOUT:-}" && "$connect_timeout" != "$FAKE_CURL_EXPECT_CONNECT_TIMEOUT" ]]; then
              echo "expected --connect-timeout $FAKE_CURL_EXPECT_CONNECT_TIMEOUT, got ${connect_timeout:-<missing>}" >&2
              exit 64
            fi

            if [[ -n "${FAKE_CURL_EXPECT_MAX_TIME:-}" && "$max_time" != "$FAKE_CURL_EXPECT_MAX_TIME" ]]; then
              echo "expected --max-time $FAKE_CURL_EXPECT_MAX_TIME, got ${max_time:-<missing>}" >&2
              exit 64
            fi

            if [[ -z "$output" || -z "$url" ]]; then
              echo "fake curl requires both url and -o path" >&2
              exit 1
            fi

            fail_kind="${FAKE_CURL_FAIL_KIND:-}"
            fail_exit="${FAKE_CURL_FAIL_EXIT:-28}"
            if [[ "$fail_kind" == "models" && "$url" == */models ]]; then
              echo "curl: (28) Operation timed out" >&2
              exit "$fail_exit"
            fi
            if [[ "$fail_kind" == "invalid" && "$url" == */responses && "$auth" == "sk-invalid-test" ]]; then
              echo "curl: (28) Operation timed out" >&2
              exit "$fail_exit"
            fi
            if [[ "$fail_kind" == "live" && "$url" == */responses && "$auth" != "sk-invalid-test" ]]; then
              echo "curl: (28) Operation timed out" >&2
              exit "$fail_exit"
            fi

            if [[ "$url" == */models ]]; then
              cat >"$output" <<'EOF'
            {"data":[{"id":"gpt-test"}]}
            EOF
              exit 0
            fi

            if [[ "$url" != */responses ]]; then
              echo "unexpected fake curl url: $url" >&2
              exit 1
            fi

            if [[ "$auth" == "sk-invalid-test" ]]; then
              cat >"$output" <<'EOF'
            {"error":{"type":"invalid_request_error","code":"invalid_api_key","message":"bad key"}}
            EOF
              exit 0
            fi

            cat >"$output" <<'EOF'
            {"model":"gpt-test-live","output":[{"content":[{"type":"output_text","text":"pong"}]}]}
            EOF
            """
        ),
        encoding="utf-8",
    )
    curl_path.chmod(0o755)


def _run_script(script_path: Path, *, env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script_path)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_smoke_script_resolves_root_from_script_location(tmp_path: Path) -> None:
    repo_root = tmp_path / "relocated-review-system"
    script_dir = repo_root / "ops/scripts"
    script_dir.mkdir(parents=True)
    shutil.copy2(SCRIPT_PATH, script_dir / SCRIPT_PATH.name)
    (repo_root / "ops/.env").write_text(
        "OPENAI_API_KEY=sk-test\nBOT_OPENAI_MODEL=gpt-4.1-mini\n",
        encoding="utf-8",
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_curl(bin_dir)

    env = os.environ.copy()
    env.pop("REVIEW_SYSTEM_ROOT", None)
    env.pop("REVIEW_SYSTEM_ENV_FILE", None)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    result = _run_script(script_dir / SCRIPT_PATH.name, env=env, cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert f"repo_root={repo_root}" in result.stdout
    assert "repo_root_source=script_dir" in result.stdout
    assert f"env_file={repo_root / 'ops/.env'}" in result.stdout
    assert "env_file_source=ops_default" in result.stdout
    assert "endpoint_base_url=https://api.openai.com/v1" in result.stdout
    assert "configured_model=gpt-4.1-mini" in result.stdout
    assert "models_probe_status=ok" in result.stdout
    assert "invalid_key_probe_status=ok" in result.stdout
    assert "live_probe_model=gpt-test-live" in result.stdout
    assert "curl_connect_timeout_seconds=5" in result.stdout
    assert "curl_max_time_seconds=30" in result.stdout


def test_smoke_script_respects_root_and_env_overrides(tmp_path: Path) -> None:
    repo_root = tmp_path / "override-review-system"
    (repo_root / "ops").mkdir(parents=True)
    (repo_root / "ops/.env").write_text(
        "OPENAI_API_KEY=sk-root\nBOT_OPENAI_MODEL=gpt-root\n",
        encoding="utf-8",
    )
    env_file = tmp_path / "custom.env"
    env_file.write_text(
        "OPENAI_API_KEY=sk-override\nBOT_OPENAI_MODEL=gpt-override\n",
        encoding="utf-8",
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_curl(bin_dir)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["REVIEW_SYSTEM_ROOT"] = str(repo_root)
    env["REVIEW_SYSTEM_ENV_FILE"] = str(env_file)

    result = _run_script(SCRIPT_PATH, env=env, cwd=ROOT)

    assert result.returncode == 0, result.stderr
    assert f"repo_root={repo_root}" in result.stdout
    assert "repo_root_source=env" in result.stdout
    assert f"env_file={env_file}" in result.stdout
    assert "env_file_source=env" in result.stdout
    assert "endpoint_base_url=https://api.openai.com/v1" in result.stdout
    assert "configured_model=gpt-override" in result.stdout
    assert "live_probe_model=gpt-test-live" in result.stdout


def test_smoke_script_skips_invalid_key_probe_for_non_default_base_url(tmp_path: Path) -> None:
    repo_root = tmp_path / "local-backend-review-system"
    script_dir = repo_root / "ops/scripts"
    script_dir.mkdir(parents=True)
    shutil.copy2(SCRIPT_PATH, script_dir / SCRIPT_PATH.name)
    (repo_root / "ops/.env").write_text(
        "OPENAI_API_KEY=sk-local-test\n"
        "BOT_OPENAI_MODEL=local-model\n"
        "BOT_OPENAI_BASE_URL=http://127.0.0.1:11434/v1/\n",
        encoding="utf-8",
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_curl(bin_dir)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    result = _run_script(script_dir / SCRIPT_PATH.name, env=env, cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert "endpoint_base_url=http://127.0.0.1:11434/v1" in result.stdout
    assert "models_probe_status=ok" in result.stdout
    assert "invalid_key_probe_status=skipped_non_default_base_url" in result.stdout
    assert "live_probe_model=gpt-test-live" in result.stdout


def test_smoke_script_passes_configured_timeout_flags_to_curl(tmp_path: Path) -> None:
    repo_root = tmp_path / "timeout-flags-review-system"
    script_dir = repo_root / "ops/scripts"
    script_dir.mkdir(parents=True)
    shutil.copy2(SCRIPT_PATH, script_dir / SCRIPT_PATH.name)
    (repo_root / "ops/.env").write_text(
        "OPENAI_API_KEY=sk-test\nBOT_OPENAI_MODEL=gpt-timeout\n",
        encoding="utf-8",
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_curl(bin_dir)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["OPENAI_DIRECT_SMOKE_CONNECT_TIMEOUT_SECONDS"] = "0.25"
    env["OPENAI_DIRECT_SMOKE_MAX_TIME_SECONDS"] = "0.75"
    env["FAKE_CURL_EXPECT_CONNECT_TIMEOUT"] = "0.25"
    env["FAKE_CURL_EXPECT_MAX_TIME"] = "0.75"

    result = _run_script(script_dir / SCRIPT_PATH.name, env=env, cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert "curl_connect_timeout_seconds=0.25" in result.stdout
    assert "curl_max_time_seconds=0.75" in result.stdout
    assert "live_probe_model=gpt-test-live" in result.stdout


def test_smoke_script_reports_models_probe_curl_timeout_exit(tmp_path: Path) -> None:
    repo_root = tmp_path / "models-timeout-review-system"
    script_dir = repo_root / "ops/scripts"
    script_dir.mkdir(parents=True)
    shutil.copy2(SCRIPT_PATH, script_dir / SCRIPT_PATH.name)
    (repo_root / "ops/.env").write_text(
        "OPENAI_API_KEY=sk-test\nBOT_OPENAI_MODEL=gpt-timeout\n",
        encoding="utf-8",
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_curl(bin_dir)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["FAKE_CURL_FAIL_KIND"] = "models"

    result = _run_script(script_dir / SCRIPT_PATH.name, env=env, cwd=tmp_path)

    assert result.returncode == 28
    assert "models_probe_curl_exit=28" in result.stdout
    assert "models_probe_status=ok" not in result.stdout
    assert "curl: (28) Operation timed out" in result.stderr


def test_smoke_script_reports_live_probe_curl_timeout_exit_after_prechecks(tmp_path: Path) -> None:
    repo_root = tmp_path / "live-timeout-review-system"
    script_dir = repo_root / "ops/scripts"
    script_dir.mkdir(parents=True)
    shutil.copy2(SCRIPT_PATH, script_dir / SCRIPT_PATH.name)
    (repo_root / "ops/.env").write_text(
        "OPENAI_API_KEY=sk-test\nBOT_OPENAI_MODEL=gpt-timeout\n",
        encoding="utf-8",
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_curl(bin_dir)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["FAKE_CURL_FAIL_KIND"] = "live"

    result = _run_script(script_dir / SCRIPT_PATH.name, env=env, cwd=tmp_path)

    assert result.returncode == 28
    assert "models_probe_status=ok" in result.stdout
    assert "invalid_key_probe_status=ok" in result.stdout
    assert "live_probe_curl_exit=28" in result.stdout
    assert "live_probe_model=gpt-test-live" not in result.stdout
    assert "curl: (28) Operation timed out" in result.stderr
