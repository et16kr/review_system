#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from uuid import uuid4
from pathlib import Path
from urllib import parse, request

from attach_local_gitlab_bot import (
    ENV_PATH,
    get_bot_state,
    load_env,
    rebuild_bot_services,
    update_env,
)
from bootstrap_local_gitlab_tde_review import (
    OPS_DIR,
    api_json,
    compose,
    create_project_via_api,
    create_root_personal_access_token,
    ensure_directories,
    ensure_root_user,
    wait_for_gitlab,
)
from replay_local_gitlab_tde_review import (
    attach_bot,
    add_human_reply,
    list_discussions,
    trigger_sync,
    wait_for_feedback_change,
)

ROOT = Path("/home/et16/work/review_system")
WORKTREE_ROOT = ROOT / "ops" / ".tmp" / "multilang-smoke-repo"

BASE_MARKDOWN = """# Release Notes

- Safe baseline document for mixed-language smoke.
"""

FEATURE_MARKDOWN = """# Release Notes

- Mixed-language smoke fixture
- Markdown file should stay unreviewable.
"""

BASE_GITLAB_CI = """image: python:3.12

deploy_job:
  stage: deploy
  script:
    - ./deploy.sh
"""

BASE_SQL = """select
  user_id,
  date_trunc('day', created_at) as day_bucket,
  count(*) as total_rows
from events
where created_at >= current_date - interval '7 day'
group by 1, 2;
"""

BASE_FASTAPI = """import httpx
from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/items")
async def create_item(request: Request):
    payload = await request.json()
    async with httpx.AsyncClient(timeout=5) as client:
        upstream = await client.get("https://example.com/health")
    return {"ok": upstream.is_success, "payload": payload}
"""


def run(cmd: list[str], *, cwd: Path, capture: bool = False) -> str:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd),
        check=True,
        text=True,
        capture_output=capture,
    )
    return completed.stdout.strip() if capture else ""


def gitlab_base_url() -> str:
    env_file = OPS_DIR / ".env"
    if not env_file.exists():
        raise SystemExit("ops/.env not found. Copy ops/.env.example to ops/.env first.")
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("LOCAL_GITLAB_EXTERNAL_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    return "http://127.0.0.1:18929"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a mixed-language local GitLab smoke with markdown/yaml/sql/framework files."
    )
    parser.add_argument("--project-ref", default="root/review-system-multilang-smoke")
    parser.add_argument("--target-branch", default="smoke_base")
    parser.add_argument("--source-branch", default="smoke_feature")
    parser.add_argument("--skip-start", action="store_true", help="Do not start local GitLab compose.")
    parser.add_argument(
        "--skip-reset-bot-state",
        action="store_true",
        help="Keep existing bot DB rows instead of truncating before attach.",
    )
    parser.add_argument(
        "--bootstrap-token-name",
        default="review-system-multilang-smoke-bootstrap",
        help="Root personal access token name used while preparing the GitLab project.",
    )
    parser.add_argument(
        "--bot-token-name",
        default="review-bot-runtime-multilang",
        help="Token name passed while attaching review-bot.",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional path to write a JSON result artifact.",
    )
    parser.add_argument(
        "--skip-provider-restore",
        action="store_true",
        help=(
            "Leave BOT_PROVIDER/BOT_FALLBACK_PROVIDER as-is after the smoke. "
            "Useful while iterating on the mixed-language fixture to avoid an extra bot rebuild."
        ),
    )
    return parser.parse_args()


def _write_files(root: Path, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _set_authenticated_remote(repo_path: Path, repo_http_url: str, token: str) -> None:
    authenticated = repo_http_url.replace("http://", f"http://root:{token}@", 1)
    existing = run(["git", "remote"], cwd=repo_path, capture=True).splitlines()
    if "gitlab-local" in existing:
        run(["git", "remote", "set-url", "gitlab-local", authenticated], cwd=repo_path)
    else:
        run(["git", "remote", "add", "gitlab-local", authenticated], cwd=repo_path)


def _prepare_local_repo(
    *,
    repo_path: Path,
    target_branch: str,
    source_branch: str,
) -> None:
    if repo_path.exists():
        shutil.rmtree(repo_path)
    repo_path.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-b", target_branch], cwd=repo_path)
    run(["git", "config", "user.name", "Review Bot Smoke"], cwd=repo_path)
    run(["git", "config", "user.email", "review-bot-smoke@example.local"], cwd=repo_path)

    _write_files(
        repo_path,
        {
            "docs/release_notes.md": BASE_MARKDOWN,
            ".gitlab-ci.yml": BASE_GITLAB_CI,
            "warehouse/daily_rollup.sql": BASE_SQL,
            "api/routes/items.py": BASE_FASTAPI,
        },
    )
    run(["git", "add", "."], cwd=repo_path)
    run(["git", "commit", "-m", "seed safe baseline"], cwd=repo_path)

    run(["git", "checkout", "-b", source_branch], cwd=repo_path)
    _write_files(
        repo_path,
        {
            "docs/release_notes.md": FEATURE_MARKDOWN,
            ".gitlab-ci.yml": (
                ROOT / "review-engine" / "examples" / "multilang" / "gitlab_remote" / ".gitlab-ci.yml"
            ).read_text(encoding="utf-8"),
            "warehouse/daily_rollup.sql": (
                ROOT / "review-engine" / "examples" / "multilang" / "warehouse" / "daily_rollup.sql"
            ).read_text(encoding="utf-8"),
            "api/routes/items.py": (
                ROOT / "review-engine" / "examples" / "multilang" / "python_fastapi_service.py"
            ).read_text(encoding="utf-8"),
        },
    )
    run(["git", "add", "."], cwd=repo_path)
    run(["git", "commit", "-m", "add mixed-language review targets"], cwd=repo_path)


def _push_fixture_branches(
    *,
    repo_path: Path,
    repo_http_url: str,
    token: str,
    target_branch: str,
    source_branch: str,
) -> None:
    _set_authenticated_remote(repo_path, repo_http_url, token)
    run(["git", "push", "--force", "gitlab-local", f"{target_branch}:{target_branch}"], cwd=repo_path)
    run(["git", "push", "--force", "gitlab-local", f"{source_branch}:{source_branch}"], cwd=repo_path)


def _delete_open_merge_requests(
    *,
    base_url: str,
    token: str,
    project_id: int,
    source_branch: str,
    target_branch: str,
) -> list[int]:
    merge_requests = api_json(
        "GET",
        (
            f"{base_url.rstrip('/')}/api/v4/projects/{project_id}/merge_requests"
            f"?state=opened&source_branch={parse.quote(source_branch)}"
            f"&target_branch={parse.quote(target_branch)}"
        ),
        token,
    )
    deleted_iids: list[int] = []
    for merge_request in merge_requests or []:
        api_json(
            "DELETE",
            (
                f"{base_url.rstrip('/')}/api/v4/projects/{project_id}/merge_requests/"
                f"{merge_request['iid']}"
            ),
            token,
        )
        deleted_iids.append(int(merge_request["iid"]))
    return deleted_iids


def _create_merge_request(
    *,
    base_url: str,
    token: str,
    project_id: int,
    source_branch: str,
    target_branch: str,
) -> dict:
    return api_json(
        "POST",
        f"{base_url.rstrip('/')}/api/v4/projects/{project_id}/merge_requests",
        token,
        {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": "Mixed-language smoke review",
            "description": (
                "Mixed-language smoke fixture with markdown, GitLab CI YAML, analytics SQL, and FastAPI."
            ),
            "remove_source_branch": False,
        },
    )


def _fetch_wrong_language_feedback(*, project_ref: str, window: str = "28d") -> dict:
    query = parse.urlencode({"project_ref": project_ref, "window": window})
    with request.urlopen(
        f"http://127.0.0.1:18081/internal/analytics/wrong-language-feedback?{query}",
        timeout=30,
    ) as response:
        return json.loads(response.read().decode("utf-8"))


def _bot_note_bodies(discussions: list[dict]) -> list[str]:
    bodies: list[str] = []
    for discussion in discussions:
        for note in discussion.get("notes") or []:
            body = str(note.get("body") or "")
            if "[봇 리뷰]" in body:
                bodies.append(body)
    return bodies


def _find_discussion_by_language(discussions: list[dict], language_id: str) -> dict | None:
    tag = f"[봇 리뷰][{language_id}]"
    for discussion in discussions:
        for note in discussion.get("notes") or []:
            body = str(note.get("body") or "")
            if tag in body:
                return discussion
    return None


def main() -> int:
    args = parse_args()
    project_ref = args.project_ref
    namespace_path, _, project_name = project_ref.rpartition("/")
    if not namespace_path or not project_name:
        raise SystemExit("project-ref must be in <namespace>/<project> form.")
    base_url = gitlab_base_url()
    branch_suffix = uuid4().hex[:8]
    target_branch = f"{args.target_branch}-{branch_suffix}"
    source_branch = f"{args.source_branch}-{branch_suffix}"
    _, env = load_env(ENV_PATH)
    original_provider = env.get("BOT_PROVIDER", "openai")
    original_fallback_provider = env.get("BOT_FALLBACK_PROVIDER", "stub")

    if not args.skip_start:
        ensure_directories()
        compose(["up", "-d"])
        wait_for_gitlab(base_url)

    ensure_root_user()
    root_token = create_root_personal_access_token(args.bootstrap_token_name)
    project = create_project_via_api(base_url, root_token, namespace_path, project_name)
    repo_http_url = str(project["http_url_to_repo"])

    _prepare_local_repo(
        repo_path=WORKTREE_ROOT,
        target_branch=target_branch,
        source_branch=source_branch,
    )
    _push_fixture_branches(
        repo_path=WORKTREE_ROOT,
        repo_http_url=repo_http_url,
        token=root_token,
        target_branch=target_branch,
        source_branch=source_branch,
    )
    deleted_mrs = _delete_open_merge_requests(
        base_url=base_url,
        token=root_token,
        project_id=int(project["id"]),
        source_branch=source_branch,
        target_branch=target_branch,
    )
    merge_request = _create_merge_request(
        base_url=base_url,
        token=root_token,
        project_id=int(project["id"]),
        source_branch=source_branch,
        target_branch=target_branch,
    )

    update_env(
        ENV_PATH,
        {
            "BOT_PROVIDER": "stub",
            "BOT_FALLBACK_PROVIDER": "stub",
        },
    )
    try:
        attach_result = attach_bot(
            project_ref=project_ref,
            mr_iid=int(merge_request["iid"]),
            token_name=args.bot_token_name,
            root_token=root_token,
            gitlab_external_url=base_url,
            skip_reset_bot_state=args.skip_reset_bot_state,
        )
        review_state = dict(attach_result["review_state"])
        discussions = list_discussions(
            base_url=base_url,
            token=root_token,
            project_ref=project_ref,
            mr_iid=int(merge_request["iid"]),
        )
        bot_bodies = _bot_note_bodies(discussions)
        required_tags = ["[봇 리뷰][yaml]", "[봇 리뷰][sql]", "[봇 리뷰][python]"]
        missing_tags = [tag for tag in required_tags if not any(tag in body for body in bot_bodies)]
        unexpected_cpp = any("[봇 리뷰][cpp]" in body for body in bot_bodies)
        if missing_tags:
            raise RuntimeError(f"Missing expected language-tagged comments: {missing_tags}")
        if unexpected_cpp:
            raise RuntimeError("Mixed-language smoke unexpectedly produced a cpp-tagged review comment.")

        yaml_discussion = _find_discussion_by_language(discussions, "yaml")
        if yaml_discussion is None:
            raise RuntimeError("Could not find a yaml-tagged discussion for wrong-language feedback flow.")

        before_sync_state = get_bot_state(project_ref, int(merge_request["iid"]))
        add_human_reply(
            base_url=base_url,
            token=root_token,
            project_ref=project_ref,
            mr_iid=int(merge_request["iid"]),
            discussion_id=str(yaml_discussion["id"]),
            body="@review-bot wrong-language markdown\n이 스레드는 문서 예외 흐름 점검용입니다.",
        )
        trigger_sync(str(before_sync_state["last_review_run_id"]))
        after_sync_state = wait_for_feedback_change(
            project_ref=project_ref,
            mr_iid=int(merge_request["iid"]),
            previous_feedback_count=int(before_sync_state.get("feedback_event_count") or 0),
            previous_open_thread_count=int(before_sync_state.get("open_thread_count") or 0),
        )
        telemetry = _fetch_wrong_language_feedback(project_ref=project_ref, window="28d")
        if not any(
            item.get("detected_language_id") == "yaml"
            and item.get("expected_language_id") == "markdown"
            for item in telemetry.get("top_language_pairs", [])
        ):
            raise RuntimeError(
                "wrong-language telemetry did not record the expected yaml -> markdown pair."
            )

        result = {
            "project_ref": project_ref,
            "merge_request_iid": int(merge_request["iid"]),
            "merge_request_url": f"{project['web_url']}/-/merge_requests/{merge_request['iid']}",
            "target_branch": target_branch,
            "source_branch": source_branch,
            "deleted_merge_requests": deleted_mrs,
            "review_state": review_state,
            "after_sync_state": after_sync_state,
            "required_tags": required_tags,
            "bot_comment_count": len(bot_bodies),
            "wrong_language_pairs": telemetry.get("top_language_pairs", []),
            "triage_candidates": telemetry.get("triage_candidates", []),
        }

        if args.json_output:
            output_path = Path(args.json_output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    finally:
        if (
            not args.skip_provider_restore
            and (
            original_provider != "stub"
            or original_fallback_provider != "stub"
            )
        ):
            update_env(
                ENV_PATH,
                {
                    "BOT_PROVIDER": original_provider,
                    "BOT_FALLBACK_PROVIDER": original_fallback_provider,
                },
            )
            rebuild_bot_services()


if __name__ == "__main__":
    raise SystemExit(main())
