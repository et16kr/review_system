#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib import error, parse, request

ROOT = Path("/home/et16/work/review_system")
OPS_DIR = ROOT / "ops"
DOCKER_COMPOSE = OPS_DIR / "docker-compose.yml"
GITLAB_COMPOSE = OPS_DIR / "gitlab-local-compose.yml"
ENV_PATH = OPS_DIR / ".env"


def run(cmd: list[str], *, capture: bool = False) -> str:
    completed = subprocess.run(
        cmd,
        cwd=str(ROOT),
        check=True,
        text=True,
        capture_output=capture,
    )
    return completed.stdout.strip() if capture else ""


def compose(args: list[str], *, capture: bool = False) -> str:
    return run(
        [
            "docker",
            "compose",
            "-f",
            str(DOCKER_COMPOSE),
            "--env-file",
            str(ENV_PATH),
            *args,
        ],
        capture=capture,
    )


def gitlab_compose(args: list[str], *, capture: bool = False) -> str:
    return run(
        [
            "docker",
            "compose",
            "-f",
            str(GITLAB_COMPOSE),
            "--env-file",
            str(ENV_PATH),
            *args,
        ],
        capture=capture,
    )


def load_env(path: Path) -> tuple[list[str], dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    mapping: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        mapping[key] = value
    return lines, mapping


def update_env(path: Path, updates: dict[str, str]) -> None:
    lines, _ = load_env(path)
    pending = dict(updates)
    new_lines: list[str] = []
    for line in lines:
        if "=" not in line or line.lstrip().startswith("#"):
            new_lines.append(line)
            continue
        key, _ = line.split("=", 1)
        if key in pending:
            new_lines.append(f"{key}={pending.pop(key)}")
        else:
            new_lines.append(line)
    for key, value in pending.items():
        new_lines.append(f"{key}={value}")
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def run_in_gitlab_container(script: str) -> str:
    return gitlab_compose(
        ["exec", "-T", "gitlab", "gitlab-rails", "runner", script],
        capture=True,
    )


def ensure_gitlab_allows_local_webhooks() -> None:
    ruby = """
settings = ApplicationSetting.current
settings.update!(allow_local_requests_from_web_hooks_and_services: true)
puts settings.allow_local_requests_from_web_hooks_and_services
"""
    run_in_gitlab_container(ruby)


def ensure_local_user(
    *,
    username: str,
    email: str,
    password: str,
    name: str,
    admin: bool,
) -> dict[str, str | int | bool]:
    ruby = f"""
org = Organizations::Organization.first
raise 'default organization not found' unless org
user = User.find_by_username({username!r})
if user.nil?
  params = {{
    username: {username!r},
    email: {email!r},
    name: {name!r},
    password: {password!r},
    password_confirmation: {password!r},
    organization_id: org.id,
    admin: {str(admin).lower()},
    skip_confirmation: true
  }}
  result = Users::CreateService.new(nil, params).execute
  raise result.message unless result.success?
  user = result.payload[:user]
end
user.email = {email!r}
user.name = {name!r}
user.password = {password!r}
user.password_confirmation = {password!r}
user.admin = {str(admin).lower()}
user.confirm if user.respond_to?(:confirm) && !user.confirmed?
user.save!
payload = {{
  "id" => user.id,
  "username" => user.username,
  "admin" => user.admin,
  "confirmed" => user.confirmed?
}}
puts(payload.to_json)
"""
    raw = run_in_gitlab_container(ruby).strip().splitlines()[-1].strip()
    if not raw:
        raise RuntimeError(f"Failed to ensure local GitLab user: {username}")
    return json.loads(raw)


def create_personal_access_token(username: str, token_name: str) -> str:
    ruby = f"""
require 'securerandom'
user = User.find_by_username({username!r})
raise 'user not found' unless user
existing = user.personal_access_tokens.active.find_by(name: {token_name!r})
existing&.revoke!
token_value = SecureRandom.hex(20)
pat = user.personal_access_tokens.create!(
  name: {token_name!r},
  scopes: [:api, :read_api, :read_repository, :write_repository],
  expires_at: 30.days.from_now
)
pat.set_token(token_value)
pat.save!
puts token_value
"""
    value = run_in_gitlab_container(ruby).strip().splitlines()[-1].strip()
    if not value:
        raise RuntimeError("Failed to create GitLab personal access token.")
    return value


def create_user_personal_access_token(
    *,
    base_url: str,
    admin_token: str,
    user_id: int,
    token_name: str,
) -> str:
    payload = api_json(
        "POST",
        f"{base_url.rstrip('/')}/api/v4/users/{user_id}/personal_access_tokens",
        admin_token,
        {
            "name": token_name,
            "expires_at": (date.today() + timedelta(days=30)).isoformat(),
            "scopes": ["api", "read_api", "read_repository", "write_repository"],
        },
    )
    token = (payload or {}).get("token")
    if not token:
        raise RuntimeError(f"Failed to create GitLab personal access token for user_id={user_id}")
    return str(token)


def api_json(method: str, url: str, token: str, payload: dict | None = None):
    body = None
    headers = {"PRIVATE-TOKEN": token}
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, method=method, headers=headers, data=body)
    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitLab API {method} {url} failed: {exc.code} {detail}") from exc


def get_project(base_url: str, token: str, project_ref: str) -> dict:
    payload = api_json(
        "GET",
        f"{base_url.rstrip('/')}/api/v4/projects/{parse.quote(project_ref, safe='')}",
        token,
    )
    if not payload:
        raise RuntimeError(f"Project not found: {project_ref}")
    return payload


def ensure_project_member(
    *,
    base_url: str,
    token: str,
    project_ref: str,
    user_id: int,
    access_level: int,
) -> dict:
    encoded_project = parse.quote(project_ref, safe="")
    member_url = (
        f"{base_url.rstrip('/')}/api/v4/projects/{encoded_project}/members/{user_id}"
    )
    all_member_url = (
        f"{base_url.rstrip('/')}/api/v4/projects/{encoded_project}/members/all/{user_id}"
    )
    try:
        payload = api_json("GET", all_member_url, token)
        if int(payload.get("access_level", 0)) == access_level:
            return payload
        return api_json(
            "PUT",
            member_url,
            token,
            {"access_level": access_level},
        )
    except RuntimeError as exc:
        if "404" not in str(exc):
            raise
    return api_json(
        "POST",
        f"{base_url.rstrip('/')}/api/v4/projects/{encoded_project}/members",
        token,
        {"user_id": user_id, "access_level": access_level},
    )


def list_project_hooks(base_url: str, token: str, project_ref: str) -> list[dict]:
    payload = api_json(
        "GET",
        f"{base_url.rstrip('/')}/api/v4/projects/{parse.quote(project_ref, safe='')}/hooks",
        token,
    )
    return payload or []


def ensure_review_request_webhook(
    *,
    base_url: str,
    token: str,
    project_ref: str,
    webhook_url: str,
    secret: str,
) -> dict:
    hooks = list_project_hooks(base_url, token, project_ref)
    payload = {
        "url": webhook_url,
        "token": secret,
        "enable_ssl_verification": False,
        "merge_requests_events": False,
        "push_events": False,
        "issues_events": False,
        "note_events": True,
    }
    for hook in hooks:
        if hook.get("url") == webhook_url:
            hook_id = hook["id"]
            return api_json(
                "PUT",
                (
                    f"{base_url.rstrip('/')}/api/v4/projects/"
                    f"{parse.quote(project_ref, safe='')}/hooks/{hook_id}"
                ),
                token,
                payload,
            )
    return api_json(
        "POST",
        f"{base_url.rstrip('/')}/api/v4/projects/{parse.quote(project_ref, safe='')}/hooks",
        token,
        payload,
    )


def reset_bot_state() -> None:
    truncate_sql = (
        "TRUNCATE TABLE dead_letter_records, feedback_events, thread_sync_states, publication_states, "
        "finding_decisions, finding_evidences, review_runs, review_requests "
        "RESTART IDENTITY CASCADE;"
    )
    compose(
        [
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "review",
            "-d",
            "review",
            "-c",
            truncate_sql,
        ]
    )


def rebuild_bot_services() -> None:
    compose(["up", "-d", "--build", "review-bot-api", "review-bot-worker"])


def wait_for_http_ok(url: str, timeout_seconds: int = 120) -> None:
    deadline = time.time() + timeout_seconds
    last_error = "not started"
    while time.time() < deadline:
        try:
            with request.urlopen(url, timeout=10) as response:
                if 200 <= response.status < 300:
                    return
                last_error = f"unexpected status {response.status}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def request_review_via_mention(
    *,
    base_url: str,
    token: str,
    project_ref: str,
    pr_id: int,
    bot_username: str,
    body: str | None = None,
) -> dict:
    encoded_project = parse.quote(project_ref, safe="")
    note_body = body or f"@{bot_username} review 부탁드립니다."
    payload = json.dumps({"body": note_body}).encode("utf-8")
    req = request.Request(
        f"{base_url.rstrip('/')}/api/v4/projects/{encoded_project}/merge_requests/{pr_id}/notes",
        method="POST",
        headers={"PRIVATE-TOKEN": token, "Content-Type": "application/json"},
        data=payload,
    )
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_bot_state(project_ref: str, pr_id: int) -> dict:
    encoded_project_ref = parse.quote(project_ref, safe="")
    state_url = (
        "http://127.0.0.1:18081/internal/review/requests/"
        f"gitlab/{encoded_project_ref}/{pr_id}"
    )
    with request.urlopen(state_url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_review_completion(project_ref: str, pr_id: int, timeout_seconds: int = 300) -> dict:
    deadline = time.time() + timeout_seconds
    last_state: dict | None = None
    while time.time() < deadline:
        last_state = get_bot_state(project_ref, pr_id)
        if last_state.get("last_status") in {"success", "partial", "failed"}:
            return last_state
        time.sleep(3)
    raise RuntimeError(f"Timed out waiting for review completion: {last_state}")


def count_gitlab_notes(base_url: str, token: str, project_ref: str, pr_id: int) -> int:
    notes = api_json(
        "GET",
        (
            f"{base_url.rstrip('/')}/api/v4/projects/{parse.quote(project_ref, safe='')}"
            f"/merge_requests/{pr_id}/notes?per_page=100"
        ),
        token,
    )
    discussions = api_json(
        "GET",
        (
            f"{base_url.rstrip('/')}/api/v4/projects/{parse.quote(project_ref, safe='')}"
            f"/merge_requests/{pr_id}/discussions?per_page=100"
        ),
        token,
    )
    note_count = len(notes or [])
    discussion_note_count = sum(len(item.get("notes") or []) for item in (discussions or []))
    return note_count + discussion_note_count


def delete_existing_bot_comments(base_url: str, token: str, project_ref: str, pr_id: int) -> None:
    encoded_project = parse.quote(project_ref, safe="")
    notes = api_json(
        "GET",
        f"{base_url.rstrip('/')}/api/v4/projects/{encoded_project}/merge_requests/{pr_id}/notes?per_page=100",
        token,
    )
    discussions = api_json(
        "GET",
        (
            f"{base_url.rstrip('/')}/api/v4/projects/{encoded_project}"
            f"/merge_requests/{pr_id}/discussions?per_page=100"
        ),
        token,
    )

    for note in notes or []:
        if "[봇 리뷰]" not in (note.get("body") or ""):
            continue
        try:
            api_json(
                "DELETE",
                (
                    f"{base_url.rstrip('/')}/api/v4/projects/{encoded_project}"
                    f"/merge_requests/{pr_id}/notes/{note['id']}"
                ),
                token,
            )
        except RuntimeError:
            continue

    for discussion in discussions or []:
        discussion_id = discussion.get("id")
        for note in discussion.get("notes") or []:
            if "[봇 리뷰]" not in (note.get("body") or ""):
                continue
            try:
                api_json(
                    "DELETE",
                    (
                        f"{base_url.rstrip('/')}/api/v4/projects/{encoded_project}"
                        f"/merge_requests/{pr_id}/discussions/{discussion_id}/notes/{note['id']}"
                    ),
                    token,
                )
            except RuntimeError:
                continue


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Attach the local GitLab MR to the review bot.")
    parser.add_argument("--project-ref", default="root/altidev4-review")
    parser.add_argument("--mr-iid", type=int, default=1)
    parser.add_argument("--token-name", default="review-bot-runtime")
    parser.add_argument(
        "--trigger-initial-review",
        action="store_true",
        help="Post an @review-bot MR comment after attachment to request the first review.",
    )
    parser.add_argument(
        "--skip-reset-bot-state",
        action="store_true",
        help="Keep existing review-bot DB rows instead of truncating them.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not ENV_PATH.exists():
        raise SystemExit("ops/.env not found. Copy ops/.env.example to ops/.env first.")

    _, env = load_env(ENV_PATH)
    gitlab_external_url = env.get("LOCAL_GITLAB_EXTERNAL_URL", "http://127.0.0.1:18929").rstrip("/")
    gitlab_internal_url = env.get("LOCAL_GITLAB_INTERNAL_URL", "http://review-system-gitlab").rstrip("/")
    webhook_url = env.get(
        "LOCAL_GITLAB_BOT_WEBHOOK_URL",
        "http://review-bot-api:18081/webhooks/gitlab/merge-request",
    ).rstrip("/")
    bot_username = env.get("LOCAL_GITLAB_BOT_USERNAME", "review-bot")
    bot_email = env.get("LOCAL_GITLAB_BOT_EMAIL", "review-bot@example.local")
    bot_password = env.get("LOCAL_GITLAB_BOT_PASSWORD", "B9Qv7!Lm2#Xa4Tc8Hp")

    ensure_gitlab_allows_local_webhooks()
    root_token = create_personal_access_token("root", "review-system-bootstrap-admin")
    bot_user = ensure_local_user(
        username=bot_username,
        email=bot_email,
        password=bot_password,
        name="Review Bot",
        admin=False,
    )
    project = get_project(gitlab_external_url, root_token, args.project_ref)
    ensure_project_member(
        base_url=gitlab_external_url,
        token=root_token,
        project_ref=args.project_ref,
        user_id=int(bot_user["id"]),
        access_level=30,
    )
    token = create_user_personal_access_token(
        base_url=gitlab_external_url,
        admin_token=root_token,
        user_id=int(bot_user["id"]),
        token_name=args.token_name,
    )
    secret = secrets.token_hex(16)

    update_env(
        ENV_PATH,
        {
            "REVIEW_SYSTEM_ADAPTER": "gitlab",
            "REVIEW_SYSTEM_BASE_URL": gitlab_internal_url,
            "GITLAB_TOKEN": token,
            "GITLAB_WEBHOOK_SECRET": secret,
            "BOT_AUTHOR_NAME": bot_username,
            "LOCAL_GITLAB_BOT_USERNAME": bot_username,
            "LOCAL_GITLAB_BOT_EMAIL": bot_email,
            "LOCAL_GITLAB_BOT_PASSWORD": bot_password,
        },
    )

    rebuild_bot_services()
    wait_for_http_ok("http://127.0.0.1:18081/health")
    if not args.skip_reset_bot_state:
        reset_bot_state()
    delete_existing_bot_comments(gitlab_external_url, root_token, args.project_ref, args.mr_iid)

    hook = ensure_review_request_webhook(
        base_url=gitlab_external_url,
        token=root_token,
        project_ref=args.project_ref,
        webhook_url=webhook_url,
        secret=secret,
    )
    review_request_note = None
    state = get_bot_state(args.project_ref, args.mr_iid)
    if args.trigger_initial_review:
        review_request_note = request_review_via_mention(
            base_url=gitlab_external_url,
            token=root_token,
            project_ref=args.project_ref,
            pr_id=args.mr_iid,
            bot_username=bot_username,
        )
        state = wait_for_review_completion(args.project_ref, args.mr_iid)
    note_count = count_gitlab_notes(gitlab_external_url, root_token, args.project_ref, args.mr_iid)

    print(
        json.dumps(
            {
                "gitlab_url": gitlab_external_url,
                "project": project["path_with_namespace"],
                "merge_request_url": f"{project['web_url']}/-/merge_requests/{args.mr_iid}",
                "bot_adapter": "gitlab",
                "webhook_url": webhook_url,
                "hook_id": hook.get("id"),
                "review_request_note": review_request_note,
                "review_state": state,
                "gitlab_note_count": note_count,
                "bot_username": bot_username,
                "bot_user_id": bot_user["id"],
                "token_name": args.token_name,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
