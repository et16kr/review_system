#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib import error, parse, request


ROOT = Path("/home/et16/work/review_system")
OPS_DIR = ROOT / "ops"
LOCAL_GITLAB_COMPOSE = OPS_DIR / "gitlab-local-compose.yml"
ALTIDEV4_PATH = Path("/home/et16/work/altidev4")


def run(cmd: list[str], *, cwd: Path | None = None, capture: bool = False) -> str:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        capture_output=capture,
    )
    return completed.stdout.strip() if capture else ""


def ensure_directories() -> None:
    for path in ("gitlab/config", "gitlab/logs", "gitlab/data"):
        (OPS_DIR / path).mkdir(parents=True, exist_ok=True)


def compose(args: list[str], *, capture: bool = False) -> str:
    return run(
        ["docker", "compose", "-f", str(LOCAL_GITLAB_COMPOSE), "--env-file", str(OPS_DIR / ".env"), *args],
        cwd=ROOT,
        capture=capture,
    )


def wait_for_gitlab(base_url: str, timeout_seconds: int = 1800) -> None:
    deadline = time.time() + timeout_seconds
    last_error = "not started"
    while time.time() < deadline:
        try:
            with request.urlopen(f"{base_url.rstrip('/')}/users/sign_in", timeout=10) as response:
                if response.status == 200:
                    return
                last_error = f"unexpected status {response.status}"
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(10)
    raise RuntimeError(f"GitLab did not become ready in time: {last_error}")


def run_in_gitlab_container(script: str) -> str:
    return compose(["exec", "-T", "gitlab", "gitlab-rails", "runner", script], capture=True)


def local_root_email() -> str:
    return os.getenv("LOCAL_GITLAB_ROOT_EMAIL", "root@example.com")


def local_root_password() -> str:
    return os.getenv("LOCAL_GITLAB_ROOT_PASSWORD", "Q7m$9Lp!2Vz#4Tx@8Hc")


def ensure_root_user() -> None:
    root_email = json.dumps(local_root_email())
    root_password = json.dumps(local_root_password())
    ruby = rf"""
org = Organizations::Organization.first
raise 'default organization not found' unless org
user = User.find_by_username('root')
if user.nil?
  params = {{
    username: 'root',
    email: {root_email},
    name: 'Administrator',
    password: {root_password},
    password_confirmation: {root_password},
    organization_id: org.id,
    admin: true,
    skip_confirmation: true
  }}
  result = Users::CreateService.new(nil, params).execute
  raise result.message unless result.success?
  user = result.payload[:user]
end
user.email = {root_email}
user.name = 'Administrator'
user.password = {root_password}
user.password_confirmation = {root_password}
user.admin = true
user.confirm if user.respond_to?(:confirm) && !user.confirmed?
user.save!
puts [user.id, user.username, user.namespace_id, user.admin, user.confirmed?].join(':')
"""
    run_in_gitlab_container(ruby)


def create_root_personal_access_token(token_name: str) -> str:
    ruby = rf"""
require 'securerandom'
user = User.find_by_username('root')
raise 'root user not found' unless user
existing = user.personal_access_tokens.active.find_by(name: '{token_name}')
existing&.revoke!
token_value = SecureRandom.hex(20)
pat = user.personal_access_tokens.create!(
  name: '{token_name}',
  scopes: [:api, :read_repository, :write_repository],
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


def create_project_via_api(base_url: str, token: str, namespace_path: str, project_name: str) -> dict:
    namespace_id = find_namespace_id(base_url, token, namespace_path)
    existing = get_project(base_url, token, f"{namespace_path}/{project_name}")
    if existing is not None:
        return existing
    return api_json(
        "POST",
        f"{base_url.rstrip('/')}/api/v4/projects",
        token,
        {
            "name": project_name,
            "path": project_name,
            "namespace_id": namespace_id,
            "visibility": "private",
        },
    )


def find_namespace_id(base_url: str, token: str, namespace_path: str) -> int:
    payload = api_json(
        "GET",
        f"{base_url.rstrip('/')}/api/v4/namespaces?search={parse.quote(namespace_path.rsplit('/', 1)[-1])}&per_page=100",
        token,
    )
    for item in payload:
        if item.get("full_path") == namespace_path:
            return int(item["id"])
    raise RuntimeError(f"Namespace not found: {namespace_path}")


def get_project(base_url: str, token: str, project_ref: str) -> dict | None:
    try:
        return api_json(
            "GET",
            f"{base_url.rstrip('/')}/api/v4/projects/{parse.quote(project_ref, safe='')}",
            token,
        )
    except RuntimeError as exc:
        if "404" in str(exc):
            return None
        raise


def api_json(method: str, url: str, token: str, payload: dict | None = None):
    body = None
    headers = {"PRIVATE-TOKEN": token}
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, method=method, headers=headers, data=body)
    try:
        with request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitLab API {method} {url} failed: {exc.code} {detail}") from exc


def ensure_remote(repo_http_url: str, token: str) -> None:
    authenticated = repo_http_url.replace("http://", f"http://root:{token}@", 1)
    existing = run(["git", "-C", str(ALTIDEV4_PATH), "remote"], cwd=ROOT, capture=True).splitlines()
    if "gitlab-local" in existing:
        run(["git", "-C", str(ALTIDEV4_PATH), "remote", "set-url", "gitlab-local", authenticated], cwd=ROOT)
    else:
        run(["git", "-C", str(ALTIDEV4_PATH), "remote", "add", "gitlab-local", authenticated], cwd=ROOT)


def push_tde_branches() -> None:
    run(["git", "-C", str(ALTIDEV4_PATH), "push", "gitlab-local", "tde_base:tde_base"], cwd=ROOT)
    run(["git", "-C", str(ALTIDEV4_PATH), "push", "gitlab-local", "tde_first:tde_first"], cwd=ROOT)


def create_merge_request(base_url: str, token: str, project_id: int) -> dict:
    existing = api_json(
        "GET",
        f"{base_url.rstrip('/')}/api/v4/projects/{project_id}/merge_requests?state=opened&source_branch=tde_first&target_branch=tde_base",
        token,
    )
    if existing:
        return existing[0]
    description = run(
        [
            "python3",
            str(OPS_DIR / "scripts" / "create_gitlab_merge_request.py"),
            "--repo-path",
            str(ALTIDEV4_PATH),
            "--source-branch",
            "tde_first",
            "--target-branch",
            "tde_base",
            "--print-description-only",
        ],
        cwd=ROOT,
        capture=True,
    )
    body = {
        "source_branch": "tde_first",
        "target_branch": "tde_base",
        "title": "TDE review: tde_first -> tde_base",
        "description": description,
        "remove_source_branch": False,
    }
    return api_json(
        "POST",
        f"{base_url.rstrip('/')}/api/v4/projects/{project_id}/merge_requests",
        token,
        body,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap local GitLab and create the TDE merge request.")
    parser.add_argument("--skip-start", action="store_true", help="Do not start GitLab compose.")
    parser.add_argument("--skip-push", action="store_true", help="Do not push branches to GitLab.")
    parser.add_argument("--namespace", default="root", help="GitLab namespace path")
    parser.add_argument("--project-name", default="altidev4", help="GitLab project name/path")
    parser.add_argument(
        "--token-name",
        default="review-system-bootstrap",
        help="Personal access token name to create for root",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env_file = OPS_DIR / ".env"
    if not env_file.exists():
        raise SystemExit("ops/.env not found. Copy ops/.env.example to ops/.env first.")

    base_url = os.getenv("LOCAL_GITLAB_EXTERNAL_URL")
    if not base_url:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("LOCAL_GITLAB_EXTERNAL_URL="):
                base_url = line.split("=", 1)[1].strip()
                break
    if not base_url:
        base_url = "http://127.0.0.1:18929"

    ensure_directories()
    if not args.skip_start:
        compose(["up", "-d"])
    wait_for_gitlab(base_url)
    ensure_root_user()
    token = create_root_personal_access_token(args.token_name)
    project = create_project_via_api(base_url, token, args.namespace, args.project_name)
    if not args.skip_push:
        ensure_remote(project["http_url_to_repo"], token)
        push_tde_branches()
    mr = create_merge_request(base_url, token, int(project["id"]))
    result = {
        "gitlab_url": base_url,
        "project": project["path_with_namespace"],
        "project_web_url": project["web_url"],
        "merge_request_iid": mr["iid"],
        "merge_request_url": mr["web_url"],
        "username": "root",
        "password_source": "LOCAL_GITLAB_ROOT_PASSWORD in ops/.env",
        "token_name": args.token_name,
        "token": token,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
