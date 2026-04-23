#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, parse, request


def run_git(repo_path: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def ensure_branch_exists(repo_path: Path, branch: str) -> None:
    run_git(repo_path, "rev-parse", "--verify", branch)


def build_default_description(
    repo_path: Path,
    source_branch: str,
    target_branch: str,
) -> str:
    source_sha = run_git(repo_path, "rev-parse", "--verify", source_branch)
    target_sha = run_git(repo_path, "rev-parse", "--verify", target_branch)
    shortstat = run_git(repo_path, "diff", "--shortstat", f"{target_branch}..{source_branch}")
    changed_files = run_git(repo_path, "diff", "--name-only", f"{target_branch}..{source_branch}")
    files = [line for line in changed_files.splitlines() if line.strip()]
    preview = "\n".join(f"- `{path}`" for path in files[:20])
    remaining = max(0, len(files) - 20)
    tail = f"\n- ... and {remaining} more files" if remaining else ""
    return "\n".join(
        [
            "## Change Summary",
            f"- Source branch: `{source_branch}`",
            f"- Target branch: `{target_branch}`",
            f"- Source SHA: `{source_sha}`",
            f"- Target SHA: `{target_sha}`",
            f"- Diff stat: {shortstat}",
            "",
            "## Changed Files Preview",
            preview or "- no changed files detected",
            tail,
            "",
            "## Note",
            "- This merge request was prepared from the local smoke workspace.",
            "- Review focus: TDE implementation changes between `tde_first` and `tde_base`.",
        ]
    ).strip()


@dataclass
class GitLabProject:
    id: int
    path_with_namespace: str
    ssh_url_to_repo: str
    http_url_to_repo: str
    web_url: str


class GitLabClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def get_project(self, project_ref: str) -> GitLabProject:
        payload = self._request_json(
            "GET",
            f"/api/v4/projects/{parse.quote(project_ref, safe='')}",
        )
        return self._project_from_payload(payload)

    def find_namespace_id(self, namespace_path: str) -> int:
        search_term = namespace_path.rsplit("/", 1)[-1]
        payload = self._request_json(
            "GET",
            "/api/v4/namespaces",
            params={"search": search_term, "per_page": "100"},
        )
        for item in payload:
            if item.get("full_path") == namespace_path:
                return int(item["id"])
        raise RuntimeError(f"GitLab namespace not found: {namespace_path}")

    def create_project(
        self,
        *,
        project_name: str,
        project_path: str,
        namespace_path: str | None,
    ) -> GitLabProject:
        body: dict[str, Any] = {"name": project_name, "path": project_path}
        if namespace_path:
            body["namespace_id"] = self.find_namespace_id(namespace_path)
        payload = self._request_json("POST", "/api/v4/projects", data=body)
        return self._project_from_payload(payload)

    def ensure_project(
        self,
        *,
        project_ref: str | None,
        project_name: str,
        project_path: str,
        namespace_path: str | None,
        create_project: bool,
    ) -> GitLabProject:
        if project_ref:
            try:
                return self.get_project(project_ref)
            except RuntimeError as exc:
                if not create_project:
                    raise
                if "404" not in str(exc):
                    raise
        inferred_ref = f"{namespace_path}/{project_path}" if namespace_path else project_path
        try:
            return self.get_project(inferred_ref)
        except RuntimeError as exc:
            if not create_project and "404" in str(exc):
                raise RuntimeError(
                    f"GitLab project not found: {inferred_ref}. "
                    "Use --create-project to create it."
                ) from exc
            if "404" not in str(exc):
                raise
        return self.create_project(
            project_name=project_name,
            project_path=project_path,
            namespace_path=namespace_path,
        )

    def find_open_merge_request(
        self,
        *,
        project_id: int,
        source_branch: str,
        target_branch: str,
    ) -> dict[str, Any] | None:
        payload = self._request_json(
            "GET",
            f"/api/v4/projects/{project_id}/merge_requests",
            params={
                "state": "opened",
                "source_branch": source_branch,
                "target_branch": target_branch,
                "per_page": "20",
            },
        )
        return payload[0] if payload else None

    def create_merge_request(
        self,
        *,
        project_id: int,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
    ) -> dict[str, Any]:
        return self._request_json(
            "POST",
            f"/api/v4/projects/{project_id}/merge_requests",
            data={
                "source_branch": source_branch,
                "target_branch": target_branch,
                "title": title,
                "description": description,
                "remove_source_branch": "false",
            },
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{parse.urlencode(params)}"

        body = None
        headers = {"PRIVATE-TOKEN": self.token}
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(url, method=method, data=body, headers=headers)
        try:
            with request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitLab API {method} {url} failed: {exc.code} {payload}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"GitLab API {method} {url} failed: {exc}") from exc

    @staticmethod
    def _project_from_payload(payload: dict[str, Any]) -> GitLabProject:
        return GitLabProject(
            id=int(payload["id"]),
            path_with_namespace=str(payload["path_with_namespace"]),
            ssh_url_to_repo=str(payload["ssh_url_to_repo"]),
            http_url_to_repo=str(payload["http_url_to_repo"]),
            web_url=str(payload["web_url"]),
        )


def upsert_remote(repo_path: Path, remote_name: str, remote_url: str) -> None:
    existing = run_git(repo_path, "remote")
    remotes = {name.strip() for name in existing.splitlines() if name.strip()}
    if remote_name in remotes:
        run_git(repo_path, "remote", "set-url", remote_name, remote_url)
    else:
        run_git(repo_path, "remote", "add", remote_name, remote_url)


def push_branch(repo_path: Path, remote_name: str, branch: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_path), "push", remote_name, f"{branch}:{branch}"],
        check=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a GitLab merge request from a local git repository."
    )
    parser.add_argument("--repo-path", required=True, help="Local git repository path")
    parser.add_argument("--source-branch", required=True, help="Source branch name")
    parser.add_argument("--target-branch", required=True, help="Target branch name")
    parser.add_argument(
        "--gitlab-url",
        default=os.getenv("GITLAB_URL") or os.getenv("REVIEW_SYSTEM_BASE_URL"),
        help="GitLab base URL",
    )
    parser.add_argument(
        "--token-env",
        default="GITLAB_TOKEN",
        help="Environment variable that stores the GitLab API token",
    )
    parser.add_argument(
        "--project-ref",
        default=os.getenv("GITLAB_PROJECT_REF"),
        help="Existing GitLab project ref, for example group/repo",
    )
    parser.add_argument(
        "--namespace-path",
        default=os.getenv("GITLAB_NAMESPACE_PATH"),
        help="GitLab namespace full path, used when creating a project",
    )
    parser.add_argument(
        "--project-name",
        default="review-system-smoke",
        help="GitLab project display name",
    )
    parser.add_argument(
        "--project-path",
        default="review-system-smoke",
        help="GitLab project path slug",
    )
    parser.add_argument(
        "--remote-name",
        default="gitlab",
        help="Git remote name to create or update",
    )
    parser.add_argument(
        "--remote-kind",
        choices=["ssh", "http"],
        default="ssh",
        help="Remote URL type to configure",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Merge request title",
    )
    parser.add_argument(
        "--description-file",
        default=None,
        help="Optional markdown file to use as merge request description",
    )
    parser.add_argument(
        "--create-project",
        action="store_true",
        help="Create the GitLab project when it does not exist",
    )
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Create the merge request as Draft",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned actions without calling GitLab",
    )
    parser.add_argument(
        "--print-description-only",
        action="store_true",
        help="Print only the generated merge request description and exit",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_path = Path(args.repo_path).expanduser().resolve()
    if not repo_path.exists():
        raise SystemExit(f"Repository path does not exist: {repo_path}")

    ensure_branch_exists(repo_path, args.source_branch)
    ensure_branch_exists(repo_path, args.target_branch)

    title = args.title or f"TDE review: {args.source_branch} -> {args.target_branch}"
    if args.draft and not title.lower().startswith("draft:"):
        title = f"Draft: {title}"

    if args.description_file:
        description = Path(args.description_file).read_text(encoding="utf-8")
    else:
        description = build_default_description(repo_path, args.source_branch, args.target_branch)

    if args.print_description_only:
        print(description)
        return 0

    if args.dry_run:
        print("== GitLab Merge Request Dry Run ==")
        print(f"repo_path: {repo_path}")
        print(f"source_branch: {args.source_branch}")
        print(f"target_branch: {args.target_branch}")
        print(f"title: {title}")
        print()
        print(description)
        if args.gitlab_url:
            print()
            print(f"gitlab_url: {args.gitlab_url}")
        return 0

    if not args.gitlab_url:
        raise SystemExit("--gitlab-url or GITLAB_URL is required")

    token = os.getenv(args.token_env)
    if not token:
        raise SystemExit(f"{args.token_env} is required")

    client = GitLabClient(args.gitlab_url, token)
    project = client.ensure_project(
        project_ref=args.project_ref,
        project_name=args.project_name,
        project_path=args.project_path,
        namespace_path=args.namespace_path,
        create_project=args.create_project,
    )
    remote_url = project.ssh_url_to_repo if args.remote_kind == "ssh" else project.http_url_to_repo
    upsert_remote(repo_path, args.remote_name, remote_url)
    push_branch(repo_path, args.remote_name, args.target_branch)
    push_branch(repo_path, args.remote_name, args.source_branch)

    existing = client.find_open_merge_request(
        project_id=project.id,
        source_branch=args.source_branch,
        target_branch=args.target_branch,
    )
    if existing:
        print(json.dumps({"status": "exists", "web_url": existing.get("web_url")}, indent=2))
        return 0

    mr = client.create_merge_request(
        project_id=project.id,
        source_branch=args.source_branch,
        target_branch=args.target_branch,
        title=title,
        description=description,
    )
    print(
        json.dumps(
            {
                "status": "created",
                "project": project.path_with_namespace,
                "web_url": mr.get("web_url"),
                "iid": mr.get("iid"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
