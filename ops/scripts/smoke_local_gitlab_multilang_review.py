#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib import parse, request
from uuid import uuid4

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
    add_human_reply,
    attach_bot,
    list_discussions,
    trigger_sync,
    wait_for_feedback_change,
)

ROOT = Path("/home/et16/work/review_system")
WORKTREE_ROOT = ROOT / "ops" / ".tmp" / "multilang-smoke-repo"
FIXTURES_ROOT = ROOT / "ops" / "fixtures" / "review_smoke"
DEFAULT_FIXTURE_ID = "synthetic-mixed-language"


@dataclass(frozen=True)
class SmokeFixture:
    fixture_id: str
    root: Path
    base_files: dict[str, str]
    feature_files: dict[str, str]
    expected: dict


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


def _available_fixture_ids() -> list[str]:
    if not FIXTURES_ROOT.exists():
        return []
    return sorted(
        path.name
        for path in FIXTURES_ROOT.iterdir()
        if path.is_dir() and (path / "expected_smoke.json").exists()
    )


def _read_fixture_tree(root: Path) -> dict[str, str]:
    if not root.exists():
        raise SystemExit(f"Smoke fixture directory not found: {root}")
    files: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    if not files:
        raise SystemExit(f"Smoke fixture directory is empty: {root}")
    return files


def load_smoke_fixture(fixture_id: str) -> SmokeFixture:
    normalized_fixture_id = fixture_id.strip()
    if normalized_fixture_id in {"default", "synthetic", "mixed-language"}:
        normalized_fixture_id = DEFAULT_FIXTURE_ID

    fixture_root = FIXTURES_ROOT / normalized_fixture_id
    expected_path = fixture_root / "expected_smoke.json"
    if not expected_path.exists():
        available = ", ".join(_available_fixture_ids()) or "(none)"
        raise SystemExit(
            f"Unknown smoke fixture: {fixture_id}. Available fixtures: {available}"
        )

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    expected_fixture_id = str(expected.get("fixture_id") or normalized_fixture_id)
    if expected_fixture_id != normalized_fixture_id:
        raise SystemExit(
            f"Fixture id mismatch: directory={normalized_fixture_id}, "
            f"expected_smoke.json={expected_fixture_id}"
        )

    return SmokeFixture(
        fixture_id=normalized_fixture_id,
        root=fixture_root,
        base_files=_read_fixture_tree(fixture_root / "base"),
        feature_files=_read_fixture_tree(fixture_root / "feature"),
        expected=expected,
    )


def validate_fixture_contract(fixture: SmokeFixture) -> None:
    required_paths = _as_string_list(fixture.expected.get("required_paths"))
    changed_paths = set(_changed_fixture_paths(fixture))
    missing_required_paths = [
        path for path in required_paths if path not in fixture.feature_files
    ]
    if missing_required_paths:
        raise SystemExit(
            f"{fixture.fixture_id} missing required fixture paths: {missing_required_paths}"
        )
    unchanged_required_paths = [
        path for path in required_paths if path not in changed_paths
    ]
    if unchanged_required_paths:
        raise SystemExit(
            f"{fixture.fixture_id} required fixture paths are not changed: "
            f"{unchanged_required_paths}"
        )

    expected_engine_rules = _as_rule_expectations(
        fixture.expected.get("expected_engine_rules")
    )
    empty_rule_paths = [
        path for path, rule_nos in expected_engine_rules.items() if not rule_nos
    ]
    if empty_rule_paths:
        raise SystemExit(
            f"{fixture.fixture_id} expected_engine_rules has empty rule lists: "
            f"{empty_rule_paths}"
        )
    rule_paths_not_required = [
        path for path in expected_engine_rules if path not in required_paths
    ]
    if rule_paths_not_required:
        raise SystemExit(
            f"{fixture.fixture_id} expected engine rule paths must also be required: "
            f"{rule_paths_not_required}"
        )
    missing_rule_paths = [
        path for path in expected_engine_rules if path not in fixture.feature_files
    ]
    if missing_rule_paths:
        raise SystemExit(
            f"{fixture.fixture_id} expected engine rule paths not present in feature: "
            f"{missing_rule_paths}"
        )
    unchanged_rule_paths = [
        path for path in expected_engine_rules if path not in changed_paths
    ]
    if unchanged_rule_paths:
        raise SystemExit(
            f"{fixture.fixture_id} expected engine rule paths are not changed: "
            f"{unchanged_rule_paths}"
        )

    expected_language_tags = _as_string_list(fixture.expected.get("expected_language_tags"))
    forbidden_language_tags = _as_string_list(fixture.expected.get("forbidden_language_tags"))
    overlapping_language_tags = sorted(
        set(expected_language_tags).intersection(forbidden_language_tags)
    )
    if overlapping_language_tags:
        raise SystemExit(
            f"{fixture.fixture_id} language tags are both expected and forbidden: "
            f"{overlapping_language_tags}"
        )
    minimum_review_comments = int(fixture.expected.get("minimum_review_comments") or 0)
    if minimum_review_comments < len(expected_language_tags):
        raise SystemExit(
            f"{fixture.fixture_id} minimum_review_comments={minimum_review_comments} "
            f"is lower than expected_language_tags={len(expected_language_tags)}"
        )

    wrong_language_feedback = fixture.expected.get("wrong_language_feedback")
    if wrong_language_feedback is None:
        return
    if not isinstance(wrong_language_feedback, dict):
        raise SystemExit(
            f"{fixture.fixture_id} wrong_language_feedback must be an object when set."
        )
    detected_language_id = str(
        wrong_language_feedback.get("detected_language_id") or ""
    ).strip()
    expected_language_id = str(
        wrong_language_feedback.get("expected_language_id") or ""
    ).strip()
    if not detected_language_id or not expected_language_id:
        raise SystemExit(
            f"{fixture.fixture_id} wrong_language_feedback requires detected and expected "
            "language ids."
        )
    if detected_language_id == expected_language_id:
        raise SystemExit(
            f"{fixture.fixture_id} wrong_language_feedback must change language ids."
        )
    if expected_language_tags and detected_language_id not in expected_language_tags:
        raise SystemExit(
            f"{fixture.fixture_id} wrong_language_feedback detected_language_id must be one "
            f"of expected_language_tags: {detected_language_id}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a fixture-backed mixed-language local GitLab smoke."
    )
    parser.add_argument(
        "--fixture",
        default=DEFAULT_FIXTURE_ID,
        help=f"Smoke fixture id under ops/fixtures/review_smoke (default: {DEFAULT_FIXTURE_ID}).",
    )
    parser.add_argument(
        "--project-ref",
        default=None,
        help="GitLab project ref. Defaults to the selected fixture's default_project_ref.",
    )
    parser.add_argument("--target-branch", default="smoke_base")
    parser.add_argument("--source-branch", default="smoke_feature")
    parser.add_argument(
        "--skip-start",
        action="store_true",
        help="Do not start local GitLab compose.",
    )
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
    fixture: SmokeFixture,
) -> None:
    if repo_path.exists():
        shutil.rmtree(repo_path)
    repo_path.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-b", target_branch], cwd=repo_path)
    run(["git", "config", "user.name", "Review Bot Smoke"], cwd=repo_path)
    run(["git", "config", "user.email", "review-bot-smoke@example.local"], cwd=repo_path)

    _write_files(repo_path, fixture.base_files)
    run(["git", "add", "."], cwd=repo_path)
    run(["git", "commit", "-m", "seed safe baseline"], cwd=repo_path)

    run(["git", "checkout", "-b", source_branch], cwd=repo_path)
    _write_files(repo_path, fixture.feature_files)
    run(["git", "add", "."], cwd=repo_path)
    run(["git", "commit", "-m", f"add {fixture.fixture_id} review targets"], cwd=repo_path)


def _push_fixture_branches(
    *,
    repo_path: Path,
    repo_http_url: str,
    token: str,
    target_branch: str,
    source_branch: str,
) -> None:
    _set_authenticated_remote(repo_path, repo_http_url, token)
    run(
        ["git", "push", "--force", "gitlab-local", f"{target_branch}:{target_branch}"],
        cwd=repo_path,
    )
    run(
        ["git", "push", "--force", "gitlab-local", f"{source_branch}:{source_branch}"],
        cwd=repo_path,
    )


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
    fixture: SmokeFixture,
) -> dict:
    return api_json(
        "POST",
        f"{base_url.rstrip('/')}/api/v4/projects/{project_id}/merge_requests",
        token,
        {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": str(
                fixture.expected.get("merge_request_title") or "Mixed-language smoke review"
            ),
            "description": str(
                fixture.expected.get("merge_request_description")
                or "Fixture-backed mixed-language smoke review."
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


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _as_rule_expectations(value: object) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    return {
        str(path): _as_string_list(rule_nos)
        for path, rule_nos in value.items()
        if str(path).strip()
    }


def _changed_fixture_paths(fixture: SmokeFixture) -> list[str]:
    return sorted(
        path
        for path, feature_content in fixture.feature_files.items()
        if fixture.base_files.get(path) != feature_content
    )


def validate_bot_comments(bot_bodies: list[str], expected: dict) -> dict:
    required_languages = _as_string_list(expected.get("expected_language_tags"))
    forbidden_languages = _as_string_list(expected.get("forbidden_language_tags"))
    required_tags = [f"[봇 리뷰][{language_id}]" for language_id in required_languages]
    forbidden_tags = [f"[봇 리뷰][{language_id}]" for language_id in forbidden_languages]
    missing_tags = [tag for tag in required_tags if not any(tag in body for body in bot_bodies)]
    unexpected_tags = [tag for tag in forbidden_tags if any(tag in body for body in bot_bodies)]
    minimum_review_comments = int(expected.get("minimum_review_comments") or 0)

    if len(bot_bodies) < minimum_review_comments:
        raise RuntimeError(
            f"Expected at least {minimum_review_comments} bot comments, got {len(bot_bodies)}."
        )
    if missing_tags:
        raise RuntimeError(f"Missing expected language-tagged comments: {missing_tags}")
    if unexpected_tags:
        raise RuntimeError(
            f"Smoke fixture unexpectedly produced forbidden language tags: {unexpected_tags}"
        )

    return {
        "required_tags": required_tags,
        "forbidden_tags": forbidden_tags,
        "minimum_review_comments": minimum_review_comments,
        "bot_comment_count": len(bot_bodies),
    }


def main() -> int:
    args = parse_args()
    fixture = load_smoke_fixture(args.fixture)
    validate_fixture_contract(fixture)
    project_ref = args.project_ref or str(
        fixture.expected.get("default_project_ref") or "root/review-system-multilang-smoke"
    )
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
        fixture=fixture,
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
        fixture=fixture,
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
        comment_validation = validate_bot_comments(bot_bodies, fixture.expected)

        after_sync_state = None
        telemetry: dict = {"top_language_pairs": [], "triage_candidates": []}
        wrong_language_feedback = fixture.expected.get("wrong_language_feedback")
        if isinstance(wrong_language_feedback, dict):
            detected_language_id = str(
                wrong_language_feedback.get("detected_language_id") or ""
            ).strip()
            expected_language_id = str(
                wrong_language_feedback.get("expected_language_id") or ""
            ).strip()
            if not detected_language_id or not expected_language_id:
                raise RuntimeError(
                    "wrong_language_feedback requires detected/expected language ids."
                )
            discussion = _find_discussion_by_language(discussions, detected_language_id)
            if discussion is None:
                raise RuntimeError(
                    "Could not find a "
                    f"{detected_language_id}-tagged discussion for wrong-language feedback flow."
                )

            before_sync_state = get_bot_state(project_ref, int(merge_request["iid"]))
            add_human_reply(
                base_url=base_url,
                token=root_token,
                project_ref=project_ref,
                mr_iid=int(merge_request["iid"]),
                discussion_id=str(discussion["id"]),
                body=str(
                    wrong_language_feedback.get("reply_body")
                    or f"@review-bot wrong-language {expected_language_id}"
                ),
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
                item.get("detected_language_id") == detected_language_id
                and item.get("expected_language_id") == expected_language_id
                for item in telemetry.get("top_language_pairs", [])
            ):
                raise RuntimeError(
                    "wrong-language telemetry did not record the expected "
                    f"{detected_language_id} -> {expected_language_id} pair."
                )
            triage_candidate = next(
                (
                    item
                    for item in telemetry.get("triage_candidates", [])
                    if item.get("detected_language_id") == detected_language_id
                    and item.get("expected_language_id") == expected_language_id
                ),
                None,
            )
            if triage_candidate is None:
                raise RuntimeError(
                    "wrong-language telemetry did not include a triage candidate for "
                    f"{detected_language_id} -> {expected_language_id}."
                )
            if (
                triage_candidate.get("provenance") != "smoke"
                or triage_candidate.get("triage_cause") != "synthetic_smoke"
                or triage_candidate.get("actionability") != "ignore_for_detector_backlog"
            ):
                raise RuntimeError(
                    "wrong-language smoke telemetry was not separated from detector backlog: "
                    f"{triage_candidate}"
                )

        result = {
            "fixture_id": fixture.fixture_id,
            "project_ref": project_ref,
            "merge_request_iid": int(merge_request["iid"]),
            "merge_request_url": f"{project['web_url']}/-/merge_requests/{merge_request['iid']}",
            "target_branch": target_branch,
            "source_branch": source_branch,
            "deleted_merge_requests": deleted_mrs,
            "review_state": review_state,
            "after_sync_state": after_sync_state,
            "expected_smoke": fixture.expected,
            **comment_validation,
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
            and (original_provider != "stub" or original_fallback_provider != "stub")
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
