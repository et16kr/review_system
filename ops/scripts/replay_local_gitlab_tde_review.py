#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from pathlib import Path
from urllib import parse, request

from attach_local_gitlab_bot import (
    ENV_PATH,
    create_user_personal_access_token,
    delete_existing_bot_comments,
    ensure_gitlab_allows_local_webhooks,
    ensure_local_user,
    ensure_review_request_webhook,
    ensure_project_member,
    get_bot_state,
    get_project,
    load_env,
    request_review_via_mention,
    rebuild_bot_services,
    reset_bot_state,
    wait_for_http_ok,
    wait_for_review_completion,
    update_env,
)
from bootstrap_local_gitlab_tde_review import (
    OPS_DIR,
    ROOT,
    SMOKE_REPO_PATH,
    api_json,
    compose,
    create_merge_request,
    create_project_via_api,
    create_root_personal_access_token,
    delete_matching_merge_requests,
    ensure_directories,
    ensure_remote,
    ensure_root_user,
    wait_for_gitlab,
)

DEFAULT_PROJECT_REF = "root/review-system-smoke"
DEFAULT_TARGET_BRANCH = "tde_base"
DEFAULT_SOURCE_BRANCH = "tde_first"
DEFAULT_TARGET_REF = "b5425ede8aabd45aa9edc09e7b33617aae66ce4c"
DEFAULT_SOURCE_REF = "305df15e75a4c6430c075f84877e93955eb32749"
DEFAULT_UPDATE_REFS = [
    "2d144f954952d5556eb2d99ba1b1d8fcc01c6d78",
    "d75b6b8fe7d03ecd47bb46e8c4af596d9a14ed76",
    "d6665020440e83624e01af839f4f43dcb646a580",
]


def run(cmd: list[str], *, capture: bool = False) -> str:
    import subprocess

    completed = subprocess.run(
        cmd,
        cwd=str(ROOT),
        text=True,
        check=True,
        capture_output=capture,
    )
    return completed.stdout.strip() if capture else ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset/reseed the local GitLab lifecycle smoke MR and optionally replay updates."
    )
    parser.add_argument("--project-ref", default=DEFAULT_PROJECT_REF)
    parser.add_argument("--target-branch", default=DEFAULT_TARGET_BRANCH)
    parser.add_argument("--source-branch", default=DEFAULT_SOURCE_BRANCH)
    parser.add_argument("--target-ref", default=DEFAULT_TARGET_REF)
    parser.add_argument("--source-ref", default=DEFAULT_SOURCE_REF)
    parser.add_argument(
        "--update-ref",
        action="append",
        default=[],
        help="Additional source refs to replay in order with force-push.",
    )
    parser.add_argument(
        "--replay-default-updates",
        action="store_true",
        help="Replay the built-in incremental validation sequence after baseline seeding.",
    )
    parser.add_argument("--skip-start", action="store_true", help="Do not start the local GitLab compose stack.")
    parser.add_argument(
        "--skip-attach-bot",
        action="store_true",
        help="Only recreate the GitLab project/MR; do not attach review-bot.",
    )
    parser.add_argument(
        "--skip-reset-bot-state",
        action="store_true",
        help="Pass through to attach_local_gitlab_bot.py and keep existing bot DB rows.",
    )
    parser.add_argument(
        "--reply-first-open-thread",
        action="store_true",
        help="After replay, add a human reply to the first open bot discussion.",
    )
    parser.add_argument(
        "--resolve-first-open-thread",
        action="store_true",
        help="After replay, resolve the first open bot discussion.",
    )
    parser.add_argument(
        "--reply-body",
        default="재현용 human reply 입니다.",
        help="Reply body when --reply-first-open-thread is used.",
    )
    parser.add_argument(
        "--trigger-sync-after-thread-actions",
        action="store_true",
        help="Trigger /sync for the latest run after reply/resolve actions.",
    )
    parser.add_argument(
        "--bootstrap-token-name",
        default="review-system-replay-bootstrap",
        help="Root personal access token name used while reseeding the GitLab project.",
    )
    parser.add_argument(
        "--bot-token-name",
        default="review-bot-runtime",
        help="Token name passed to attach_local_gitlab_bot.py.",
    )
    parser.add_argument(
        "--assert-default-smoke",
        action="store_true",
        help="Validate the standard baseline/update/thread-action smoke invariants and exit non-zero on failure.",
    )
    parser.add_argument(
        "--smoke-min-open-threads",
        type=int,
        default=1,
        help="Minimum baseline open thread count required by --assert-default-smoke.",
    )
    parser.add_argument(
        "--json-output",
        help="Optional path to write the final JSON result for smoke/CI artifact collection.",
    )
    return parser.parse_args()


def gitlab_base_url() -> str:
    env_file = OPS_DIR / ".env"
    if not env_file.exists():
        raise SystemExit("ops/.env not found. Copy ops/.env.example to ops/.env first.")
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("LOCAL_GITLAB_EXTERNAL_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    return "http://127.0.0.1:18929"


def split_project_ref(project_ref: str) -> tuple[str, str]:
    if "/" not in project_ref:
        raise SystemExit(f"project_ref must include namespace/path: {project_ref}")
    namespace, _, project_name = project_ref.rpartition("/")
    return namespace, project_name


def force_push_ref(*, remote: str, ref: str, branch: str) -> None:
    run(
        [
            "git",
            "-C",
            str(SMOKE_REPO_PATH),
            "push",
            "--force",
            remote,
            f"{ref}:refs/heads/{branch}",
        ]
    )


def recreate_merge_request(
    *,
    base_url: str,
    token: str,
    project_id: int,
) -> tuple[list[int], dict]:
    deleted = delete_matching_merge_requests(base_url, token, project_id)
    merge_request = create_merge_request(base_url, token, project_id)
    return deleted, merge_request


def attach_bot(
    *,
    project_ref: str,
    mr_iid: int,
    token_name: str,
    root_token: str,
    gitlab_external_url: str,
    skip_reset_bot_state: bool,
) -> dict:
    _, env = load_env(ENV_PATH)
    gitlab_internal_url = env.get("LOCAL_GITLAB_INTERNAL_URL", "http://review-system-gitlab").rstrip("/")
    webhook_url = env.get(
        "LOCAL_GITLAB_BOT_WEBHOOK_URL",
        "http://review-bot-api:18081/webhooks/gitlab/merge-request",
    ).rstrip("/")
    bot_username = env.get("LOCAL_GITLAB_BOT_USERNAME", "review-bot")
    bot_email = env.get("LOCAL_GITLAB_BOT_EMAIL", "review-bot@example.local")
    bot_password = env.get("LOCAL_GITLAB_BOT_PASSWORD", "B9Qv7!Lm2#Xa4Tc8Hp")

    ensure_gitlab_allows_local_webhooks()
    bot_user = ensure_local_user(
        username=bot_username,
        email=bot_email,
        password=bot_password,
        name="Review Bot",
        admin=False,
    )
    project = get_project(gitlab_external_url, root_token, project_ref)
    ensure_project_member(
        base_url=gitlab_external_url,
        token=root_token,
        project_ref=project_ref,
        user_id=int(bot_user["id"]),
        access_level=30,
    )
    token = create_user_personal_access_token(
        base_url=gitlab_external_url,
        admin_token=root_token,
        user_id=int(bot_user["id"]),
        token_name=token_name,
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
    if not skip_reset_bot_state:
        reset_bot_state()
    delete_existing_bot_comments(gitlab_external_url, root_token, project_ref, mr_iid)
    hook = ensure_review_request_webhook(
        base_url=gitlab_external_url,
        token=root_token,
        project_ref=project_ref,
        webhook_url=webhook_url,
        secret=secret,
    )
    request_note = request_review_via_mention(
        base_url=gitlab_external_url,
        token=root_token,
        project_ref=project_ref,
        pr_id=mr_iid,
        bot_username=bot_username,
    )
    state = wait_for_review_completion(project_ref, mr_iid)
    return {
        "gitlab_url": gitlab_external_url,
        "project": project["path_with_namespace"],
        "merge_request_url": f"{project['web_url']}/-/merge_requests/{mr_iid}",
        "bot_adapter": "gitlab",
        "webhook_url": webhook_url,
        "hook_id": hook.get("id"),
        "review_request_note": request_note,
        "review_state": state,
        "bot_username": bot_username,
        "bot_user_id": bot_user["id"],
        "token_name": token_name,
    }


def wait_for_new_review_completion(
    *,
    project_ref: str,
    mr_iid: int,
    expected_head_sha: str,
    previous_run_id: str | None,
    timeout_seconds: int = 300,
) -> dict:
    deadline = time.time() + timeout_seconds
    last_state: dict | None = None
    while time.time() < deadline:
        last_state = get_bot_state(project_ref, mr_iid)
        if last_state.get("last_head_sha") != expected_head_sha:
            time.sleep(2)
            continue
        if previous_run_id and last_state.get("last_review_run_id") == previous_run_id:
            time.sleep(2)
            continue
        if last_state.get("last_status") in {"success", "partial", "failed"}:
            return last_state
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for new review completion: {last_state}")


def list_discussions(*, base_url: str, token: str, project_ref: str, mr_iid: int) -> list[dict]:
    return api_json(
        "GET",
        (
            f"{base_url.rstrip('/')}/api/v4/projects/{parse.quote(project_ref, safe='')}"
            f"/merge_requests/{mr_iid}/discussions?per_page=100"
        ),
        token,
    ) or []


def first_open_bot_discussion(*, base_url: str, token: str, project_ref: str, mr_iid: int) -> dict | None:
    for discussion in list_discussions(
        base_url=base_url,
        token=token,
        project_ref=project_ref,
        mr_iid=mr_iid,
    ):
        if discussion.get("individual_note") or discussion.get("resolved"):
            continue
        notes = discussion.get("notes") or []
        if not notes:
            continue
        first_note = notes[0]
        if "[봇 리뷰]" not in (first_note.get("body") or ""):
            continue
        return discussion
    return None


def add_human_reply(
    *,
    base_url: str,
    token: str,
    project_ref: str,
    mr_iid: int,
    discussion_id: str,
    body: str,
) -> dict:
    return api_json(
        "POST",
        (
            f"{base_url.rstrip('/')}/api/v4/projects/{parse.quote(project_ref, safe='')}"
            f"/merge_requests/{mr_iid}/discussions/{discussion_id}/notes"
        ),
        token,
        {"body": body},
    )


def resolve_discussion(
    *,
    base_url: str,
    token: str,
    project_ref: str,
    mr_iid: int,
    discussion_id: str,
) -> dict:
    return api_json(
        "PUT",
        (
            f"{base_url.rstrip('/')}/api/v4/projects/{parse.quote(project_ref, safe='')}"
            f"/merge_requests/{mr_iid}/discussions/{discussion_id}"
        ),
        token,
        {"resolved": "true"},
    )


def trigger_sync(review_run_id: str) -> dict:
    req = request.Request(
        f"http://127.0.0.1:18081/internal/review/runs/{review_run_id}/sync",
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_feedback_change(
    *,
    project_ref: str,
    mr_iid: int,
    previous_feedback_count: int,
    previous_open_thread_count: int,
    timeout_seconds: int = 90,
) -> dict:
    deadline = time.time() + timeout_seconds
    last_state: dict | None = None
    while time.time() < deadline:
        last_state = get_bot_state(project_ref, mr_iid)
        if (
            int(last_state.get("feedback_event_count") or 0) != previous_feedback_count
            or int(last_state.get("open_thread_count") or 0) != previous_open_thread_count
        ):
            return last_state
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for sync feedback change: {last_state}")


def _as_dict(value: object, *, label: str) -> dict:
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} is missing or is not an object.")
    return value


def _as_int(value: object, *, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label} is missing or is not an integer: {value!r}") from exc


def validate_default_smoke_result(
    result: dict[str, object],
    *,
    min_open_threads: int,
) -> list[str]:
    checks: list[str] = []

    attach = _as_dict(result.get("attach"), label="attach")
    attach_state = _as_dict(attach.get("review_state"), label="attach.review_state")
    baseline_status = attach_state.get("last_status")
    if baseline_status != "success":
        raise RuntimeError(f"baseline review did not finish successfully: {baseline_status!r}")
    checks.append("baseline review completed successfully")

    failed_publications = _as_int(
        attach_state.get("failed_publication_count"),
        label="attach.review_state.failed_publication_count",
    )
    if failed_publications != 0:
        raise RuntimeError(f"baseline review has failed publications: {failed_publications}")
    checks.append("baseline review has zero failed publications")

    baseline_open_threads = _as_int(
        attach_state.get("open_thread_count"),
        label="attach.review_state.open_thread_count",
    )
    if baseline_open_threads < min_open_threads:
        raise RuntimeError(
            "baseline review did not open enough threads: "
            f"{baseline_open_threads} < {min_open_threads}"
        )
    checks.append(f"baseline review opened at least {min_open_threads} thread(s)")

    update_replays = result.get("update_replays")
    if not isinstance(update_replays, list) or not update_replays:
        raise RuntimeError("default smoke requires at least one incremental replay.")

    for index, replay in enumerate(update_replays, start=1):
        replay_state = _as_dict(
            _as_dict(replay, label=f"update_replays[{index}]").get("review_state"),
            label=f"update_replays[{index}].review_state",
        )
        replay_ref = replay.get("ref")
        if replay_state.get("last_status") != "success":
            raise RuntimeError(
                f"incremental replay #{index} did not finish successfully: "
                f"{replay_state.get('last_status')!r}"
            )
        if replay_state.get("last_head_sha") != replay_ref:
            raise RuntimeError(
                f"incremental replay #{index} ended on unexpected head: "
                f"{replay_state.get('last_head_sha')!r} != {replay_ref!r}"
            )
        replay_failed_publications = _as_int(
            replay_state.get("failed_publication_count"),
            label=f"update_replays[{index}].review_state.failed_publication_count",
        )
        if replay_failed_publications != 0:
            raise RuntimeError(
                f"incremental replay #{index} has failed publications: {replay_failed_publications}"
            )
    checks.append(f"{len(update_replays)} incremental replay(s) completed successfully")

    thread_actions = result.get("thread_actions")
    if not isinstance(thread_actions, list):
        raise RuntimeError("thread_actions is missing from smoke result.")
    action_names = {action.get("action") for action in thread_actions if isinstance(action, dict)}
    required_actions = {"reply", "resolve", "sync"}
    missing_actions = sorted(required_actions - action_names)
    if missing_actions:
        raise RuntimeError(f"default smoke requires thread actions: missing {', '.join(missing_actions)}")
    checks.append("reply/resolve/sync thread actions were executed")

    sync_action = next(
        (
            action
            for action in reversed(thread_actions)
            if isinstance(action, dict) and action.get("action") == "sync"
        ),
        None,
    )
    sync_action = _as_dict(sync_action, label="thread_actions.sync")
    state_before_sync = _as_dict(
        sync_action.get("state_before_sync"),
        label="thread_actions.sync.state_before_sync",
    )
    sync_state = _as_dict(
        sync_action.get("review_state"),
        label="thread_actions.sync.review_state",
    )

    feedback_before = _as_int(
        state_before_sync.get("feedback_event_count"),
        label="thread_actions.sync.state_before_sync.feedback_event_count",
    )
    feedback_after = _as_int(
        sync_state.get("feedback_event_count"),
        label="thread_actions.sync.review_state.feedback_event_count",
    )
    if feedback_after <= feedback_before:
        raise RuntimeError(
            "feedback count did not increase after reply/resolve + sync: "
            f"{feedback_after} <= {feedback_before}"
        )
    checks.append("feedback collection increased after sync")

    open_threads_before = _as_int(
        state_before_sync.get("open_thread_count"),
        label="thread_actions.sync.state_before_sync.open_thread_count",
    )
    open_threads_after = _as_int(
        sync_state.get("open_thread_count"),
        label="thread_actions.sync.review_state.open_thread_count",
    )
    if open_threads_after >= open_threads_before:
        raise RuntimeError(
            "open thread count did not drop after resolve + sync: "
            f"{open_threads_after} >= {open_threads_before}"
        )
    checks.append("resolved thread reduced open thread count after sync")

    return checks


def emit_result(result: dict[str, object], *, json_output: str | None) -> None:
    rendered = json.dumps(result, indent=2)
    if json_output:
        output_path = Path(json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


def main() -> int:
    args = parse_args()
    base_url = gitlab_base_url()
    namespace_path, project_name = split_project_ref(args.project_ref)
    update_refs = list(args.update_ref)
    if args.replay_default_updates:
        update_refs.extend(DEFAULT_UPDATE_REFS)

    ensure_directories()
    if not args.skip_start:
        compose(["up", "-d"])
    wait_for_gitlab(base_url)
    ensure_root_user()
    root_token = create_root_personal_access_token(args.bootstrap_token_name)
    project = create_project_via_api(base_url, root_token, namespace_path, project_name)
    ensure_remote(project["http_url_to_repo"], root_token)

    force_push_ref(remote="gitlab-local", ref=args.target_ref, branch=args.target_branch)
    force_push_ref(remote="gitlab-local", ref=args.source_ref, branch=args.source_branch)
    deleted_merge_request_iids, merge_request = recreate_merge_request(
        base_url=base_url,
        token=root_token,
        project_id=int(project["id"]),
    )

    result: dict[str, object] = {
        "gitlab_url": base_url,
        "project": project["path_with_namespace"],
        "project_web_url": project["web_url"],
        "merge_request_iid": merge_request["iid"],
        "merge_request_url": merge_request["web_url"],
        "seed": {
            "target_branch": args.target_branch,
            "target_ref": args.target_ref,
            "source_branch": args.source_branch,
            "source_ref": args.source_ref,
            "deleted_merge_requests": deleted_merge_request_iids,
        },
        "attach": None,
        "update_replays": [],
        "thread_actions": [],
    }

    if not args.skip_attach_bot:
        attach_result = attach_bot(
            project_ref=args.project_ref,
            mr_iid=int(merge_request["iid"]),
            token_name=args.bot_token_name,
            root_token=root_token,
            gitlab_external_url=base_url,
            skip_reset_bot_state=args.skip_reset_bot_state,
        )
        result["attach"] = attach_result

    for ref in update_refs:
        previous_state = (
            get_bot_state(args.project_ref, int(merge_request["iid"]))
            if not args.skip_attach_bot
            else None
        )
        force_push_ref(remote="gitlab-local", ref=ref, branch=args.source_branch)
        if args.skip_attach_bot:
            result["update_replays"].append({"ref": ref, "state": "pushed_without_bot"})
            continue
        request_note = request_review_via_mention(
            base_url=base_url,
            token=root_token,
            project_ref=args.project_ref,
            pr_id=int(merge_request["iid"]),
            bot_username=str((result.get("attach") or {}).get("bot_username") or "review-bot"),
        )
        state = wait_for_new_review_completion(
            project_ref=args.project_ref,
            mr_iid=int(merge_request["iid"]),
            expected_head_sha=ref,
            previous_run_id=(previous_state or {}).get("last_review_run_id"),
        )
        result["update_replays"].append(
            {
                "ref": ref,
                "review_request_note": request_note,
                "review_state": state,
            }
        )

    if args.reply_first_open_thread or args.resolve_first_open_thread:
        if args.skip_attach_bot:
            raise SystemExit("Thread actions require bot attachment.")
        discussion = first_open_bot_discussion(
            base_url=base_url,
            token=root_token,
            project_ref=args.project_ref,
            mr_iid=int(merge_request["iid"]),
        )
        if discussion is None:
            raise SystemExit("No open bot discussion found for thread actions.")
        if args.reply_first_open_thread:
            reply = add_human_reply(
                base_url=base_url,
                token=root_token,
                project_ref=args.project_ref,
                mr_iid=int(merge_request["iid"]),
                discussion_id=str(discussion["id"]),
                body=args.reply_body,
            )
            result["thread_actions"].append(
                {
                    "action": "reply",
                    "discussion_id": discussion["id"],
                    "note_id": reply.get("id"),
                }
            )
        if args.resolve_first_open_thread:
            resolved = resolve_discussion(
                base_url=base_url,
                token=root_token,
                project_ref=args.project_ref,
                mr_iid=int(merge_request["iid"]),
                discussion_id=str(discussion["id"]),
            )
            result["thread_actions"].append(
                {
                    "action": "resolve",
                    "discussion_id": discussion["id"],
                    "resolved": resolved.get("resolved"),
                }
            )
        if args.trigger_sync_after_thread_actions:
            state_before_sync = get_bot_state(args.project_ref, int(merge_request["iid"]))
            sync_response = trigger_sync(str(state_before_sync["last_review_run_id"]))
            synced_state = wait_for_feedback_change(
                project_ref=args.project_ref,
                mr_iid=int(merge_request["iid"]),
                previous_feedback_count=int(state_before_sync.get("feedback_event_count") or 0),
                previous_open_thread_count=int(state_before_sync.get("open_thread_count") or 0),
            )
            result["thread_actions"].append(
                {
                    "action": "sync",
                    "response": sync_response,
                    "state_before_sync": state_before_sync,
                    "review_state": synced_state,
                }
            )

    exit_code = 0
    if args.assert_default_smoke:
        try:
            checks = validate_default_smoke_result(
                result,
                min_open_threads=args.smoke_min_open_threads,
            )
            result["smoke_validation"] = {
                "passed": True,
                "checks": checks,
            }
        except RuntimeError as exc:
            result["smoke_validation"] = {
                "passed": False,
                "error": str(exc),
            }
            exit_code = 1

    emit_result(result, json_output=args.json_output)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
