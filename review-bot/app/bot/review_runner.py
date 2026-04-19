from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.clients.engine_client import EngineClient
from app.clients.platform_client import PlatformClient
from app.config import get_settings
from app.db.models import FindingPublication, ReviewFinding, ReviewRun
from app.providers.factory import build_review_comment_provider

CPP_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
HUNK_RE = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


class ReviewRunner:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.platform_client = PlatformClient(self.settings.platform_base_url)
        self.engine_client = EngineClient(self.settings.engine_base_url)
        self.provider = build_review_comment_provider()

    def run_review(self, session: Session, pr_id: int, trigger: str) -> ReviewRun:
        review_run = ReviewRun(pr_id=pr_id, trigger=trigger, status="queued")
        session.add(review_run)
        session.commit()
        session.refresh(review_run)
        return self.execute_review_run(session, review_run.id)

    def create_review_run(self, session: Session, pr_id: int, trigger: str) -> ReviewRun:
        review_run = ReviewRun(pr_id=pr_id, trigger=trigger, status="queued")
        session.add(review_run)
        session.commit()
        session.refresh(review_run)
        return review_run

    def execute_review_run(self, session: Session, review_run_id: int) -> ReviewRun:
        review_run = session.get(ReviewRun, review_run_id)
        if review_run is None:
            raise HTTPException(status_code=404, detail=f"Review run not found: {review_run_id}")

        pr_id = review_run.pr_id
        review_run.status = "running"
        session.commit()
        session.refresh(review_run)
        self._safe_post_status(pr_id, state="running", description="자동 리뷰 실행 중")
        try:
            diff_payload = self.platform_client.get_pull_request_diff(pr_id)
            review_run.head_sha = diff_payload["pull_request"]["head_sha"]
            seen_fingerprints: set[str] = set()
            publication_failures = 0
            for file_item in diff_payload["files"]:
                if not self._is_cpp_path(file_item["path"]):
                    continue
                for line_no, review_unit in self._iter_review_units(file_item["patch"]):
                    review = self.engine_client.review_diff(review_unit, top_k=8)
                    for result in review.get("results", [])[:3]:
                        issue_signature = self._issue_signature(result, review_unit)
                        fingerprint = self._fingerprint(
                            pr_id=pr_id,
                            file_path=file_item["path"],
                            line_no=line_no,
                            rule_no=result["rule_no"],
                            issue_signature=issue_signature,
                        )
                        seen_fingerprints.add(fingerprint)
                        existing = (
                            session.query(ReviewFinding)
                            .filter(
                                ReviewFinding.pr_id == pr_id,
                                ReviewFinding.fingerprint == fingerprint,
                                ReviewFinding.status.in_(
                                    ["open", "published", "failed_publication"]
                                ),
                            )
                            .one_or_none()
                        )
                        if existing is not None:
                            continue

                        draft = self.provider.build_draft(
                            file_path=file_item["path"],
                            rule_no=result["rule_no"],
                            title=result["title"],
                            summary=result["summary"],
                            rule_text=result.get("text"),
                            fix_guidance=result.get("fix_guidance"),
                            category=result.get("category"),
                            line_no=line_no,
                        )
                        target_line_no = draft.line_no if draft.line_no is not None else line_no
                        finding = ReviewFinding(
                            review_run_id=review_run.id,
                            pr_id=pr_id,
                            fingerprint=fingerprint,
                            file_path=file_item["path"],
                            line_no=target_line_no,
                            rule_no=result["rule_no"],
                            source_family=result["source_family"],
                            score=float(result["score"]),
                            severity=draft.severity,
                            confidence=draft.confidence,
                            title=draft.title,
                            summary=draft.summary,
                            suggested_fix=draft.suggested_fix,
                            status="open" if draft.should_publish else "suppressed",
                        )
                        session.add(finding)

            session.flush()
            self._resolve_missing_findings(session, pr_id, seen_fingerprints)
            published, publication_failures = self.publish_next_batch(session, pr_id, review_run.id)
            review_run.status = "partial" if publication_failures else "success"
            review_run.completed_at = datetime.now(UTC)
            description = f"자동 리뷰 완료: {published}개 finding 게시"
            self._safe_post_status(
                pr_id,
                state="partial" if publication_failures else "success",
                description=description,
            )
            session.commit()
            session.refresh(review_run)
            return review_run
        except Exception as exc:
            review_run.status = "failed"
            review_run.completed_at = datetime.now(UTC)
            review_run.error_message = str(exc)
            session.commit()
            self._safe_post_status(pr_id, state="failed", description=str(exc)[:250])
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    def publish_next_batch(
        self, session: Session, pr_id: int, review_run_id: int | None = None
    ) -> tuple[int, int]:
        if review_run_id is None:
            last_run = (
                session.query(ReviewRun)
                .filter(ReviewRun.pr_id == pr_id)
                .order_by(ReviewRun.id.desc())
                .first()
            )
            if last_run is None:
                raise HTTPException(
                    status_code=400,
                    detail="No previous review run exists for this pull request.",
                )
            review_run_id = last_run.id

        unpublished = (
            session.query(ReviewFinding)
            .filter(
                ReviewFinding.pr_id == pr_id,
                ReviewFinding.status == "open",
            )
            .order_by(ReviewFinding.score.desc(), ReviewFinding.id.asc())
            .limit(self.settings.batch_size)
            .all()
        )
        if not unpublished:
            session.commit()
            return 0, 0

        current_batch = (
            session.query(func.max(FindingPublication.batch_no))
            .filter(FindingPublication.pr_id == pr_id)
            .scalar()
        ) or 0
        batch_no = int(current_batch) + 1

        published_count = 0
        failed_count = 0
        for finding in unpublished:
            body = self._render_comment(finding)
            try:
                comment = self.platform_client.post_comment(
                    pr_id,
                    body=body,
                    file_path=finding.file_path,
                    line_no=finding.line_no,
                )
                finding.status = "published"
                finding.comment_id = comment["id"]
                finding.publication_error = None
                session.add(
                    FindingPublication(
                        pr_id=pr_id,
                        review_run_id=review_run_id,
                        finding_id=finding.id,
                        batch_no=batch_no,
                        comment_id=comment["id"],
                    )
                )
                session.commit()
                published_count += 1
            except Exception as exc:
                finding.status = "failed_publication"
                finding.publication_error = str(exc)
                session.commit()
                failed_count += 1
        return published_count, failed_count

    def build_state(self, session: Session, pr_id: int) -> dict[str, int | str | None]:
        last_run = (
            session.query(ReviewRun)
            .filter(ReviewRun.pr_id == pr_id)
            .order_by(ReviewRun.id.desc())
            .first()
        )
        published_batch_count = (
            session.query(func.max(FindingPublication.batch_no))
            .filter(FindingPublication.pr_id == pr_id)
            .scalar()
        ) or 0
        open_finding_count = (
            session.query(func.count(ReviewFinding.id))
            .filter(
                ReviewFinding.pr_id == pr_id,
                ReviewFinding.status.in_(["open", "published", "failed_publication"]),
            )
            .scalar()
        ) or 0
        resolved_finding_count = (
            session.query(func.count(ReviewFinding.id))
            .filter(ReviewFinding.pr_id == pr_id, ReviewFinding.status == "resolved")
            .scalar()
        ) or 0
        return {
            "pr_id": pr_id,
            "last_review_run_id": last_run.id if last_run else None,
            "last_head_sha": last_run.head_sha if last_run else None,
            "last_status": last_run.status if last_run else None,
            "published_batch_count": int(published_batch_count),
            "open_finding_count": int(open_finding_count),
            "resolved_finding_count": int(resolved_finding_count),
            "failed_publication_count": int(
                session.query(func.count(ReviewFinding.id))
                .filter(ReviewFinding.pr_id == pr_id, ReviewFinding.status == "failed_publication")
                .scalar()
                or 0
            ),
            "next_batch_size": self.settings.batch_size,
        }

    def _render_comment(self, finding: ReviewFinding) -> str:
        lines = [
            f"[봇 리뷰] {finding.title}",
            "",
            f"- 규칙: {finding.rule_no}",
            f"- 설명: {finding.summary}",
        ]
        if finding.suggested_fix:
            lines.append(f"- 권장 방향: {finding.suggested_fix}")
        return "\n".join(lines)

    def _resolve_missing_findings(
        self, session: Session, pr_id: int, seen_fingerprints: set[str]
    ) -> None:
        unresolved = (
            session.query(ReviewFinding)
            .filter(
                ReviewFinding.pr_id == pr_id,
                ReviewFinding.status.in_(["open", "published", "failed_publication"]),
            )
            .all()
        )
        for finding in unresolved:
            if finding.fingerprint not in seen_fingerprints:
                finding.status = "resolved"

    def _is_cpp_path(self, path: str) -> bool:
        return any(path.endswith(ext) for ext in CPP_EXTENSIONS)

    def _extract_line_no(self, patch: str) -> int | None:
        match = HUNK_RE.search(patch)
        if match is None:
            return None
        return int(match.group(1))

    def _iter_review_units(self, patch: str) -> list[tuple[int | None, str]]:
        lines = patch.splitlines()
        units: list[tuple[int | None, str]] = []
        current_header: str | None = None
        current_lines: list[str] = []
        current_line_no: int | None = None

        for line in lines:
            if line.startswith("@@"):
                if current_header is not None:
                    units.append((current_line_no, "\n".join([current_header, *current_lines])))
                current_header = line
                current_lines = []
                current_line_no = self._extract_line_no(line)
                continue
            if current_header is not None:
                current_lines.append(line)

        if current_header is not None:
            units.append((current_line_no, "\n".join([current_header, *current_lines])))

        if units:
            return units
        return [(self._extract_line_no(patch), patch)]

    def _issue_signature(self, result: dict[str, object], review_unit: str) -> str:
        changed_lines = [
            line[1:].strip()
            for line in review_unit.splitlines()
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        ]
        signature_source = " ".join(changed_lines[:3]) or review_unit
        signature_source += f"|{result['rule_no']}|{result['title']}|{result['summary']}"
        return hashlib.sha1(signature_source.encode("utf-8")).hexdigest()[:12]

    def _fingerprint(
        self,
        *,
        pr_id: int,
        file_path: str,
        line_no: int | None,
        rule_no: str,
        issue_signature: str,
    ) -> str:
        normalized_line = line_no or 0
        return f"pr{pr_id}:{file_path}:{normalized_line}:{rule_no}:{issue_signature}"

    def _safe_post_status(self, pr_id: int, *, state: str, description: str) -> None:
        try:
            self.platform_client.post_status(pr_id, state=state, description=description)
        except Exception:
            return
