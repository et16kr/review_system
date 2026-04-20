from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session

from app.clients.engine_client import EngineClient
from app.config import get_settings
from app.db.models import FindingPublication, ReviewFinding, ReviewRun
from app.providers.change_analysis import (
    classify_issue,
    extract_changed_excerpt,
    requires_direct_signal,
    select_candidate_line,
)
from app.providers.factory import build_review_comment_provider
from app.review_systems.factory import build_review_system_adapter

CPP_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
HUNK_RE = re.compile(r"@@ -(?P<old>\d+)(?:,\d+)? \+(?P<new>\d+)(?:,\d+)? @@")
MAX_LINES_PER_REVIEW_UNIT = 80


@dataclass(frozen=True)
class ChangedPatchLine:
    marker: str
    text: str
    old_line_no: int | None = None
    new_line_no: int | None = None


@dataclass(frozen=True)
class ReviewUnit:
    patch: str
    change_snippet: str
    default_line_no: int | None
    candidate_line_nos: tuple[int, ...]
    changed_lines: tuple[ChangedPatchLine, ...]


class ReviewRunner:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.review_system = build_review_system_adapter()
        # Backward-compatible alias used by existing tests and the local demo harness.
        self.platform_client = self.review_system
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
        try:
            session.refresh(review_run)
        except InvalidRequestError as exc:
            refreshed = session.get(ReviewRun, review_run_id)
            if refreshed is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Review run not found after queue start: {review_run_id}",
                ) from exc
            review_run = refreshed
        self._safe_post_status(pr_id, state="running", description="자동 리뷰 실행 중")
        try:
            diff_payload = self.platform_client.get_pull_request_diff(pr_id)
            review_run.head_sha = diff_payload["pull_request"]["head_sha"]
            seen_fingerprints: set[str] = set()
            seen_human_keys: set[str] = set()
            existing_fingerprints = self._load_existing_fingerprints(session, pr_id)
            publication_failures = 0
            for file_item in diff_payload["files"]:
                if not self._is_cpp_path(file_item["path"]):
                    continue
                for review_unit in self._iter_review_units(file_item["patch"]):
                    review = self.engine_client.review_diff(review_unit.patch, top_k=8)
                    for result in review.get("results", [])[:3]:
                        if result.get("reviewability") not in {None, "auto_review"}:
                            continue
                        if float(result.get("score", 0.0)) < self.settings.minimum_publish_score:
                            continue
                        draft = self.provider.build_draft(
                            file_path=file_item["path"],
                            rule_no=result["rule_no"],
                            title=result["title"],
                            summary=result["summary"],
                            rule_text=result.get("text"),
                            fix_guidance=result.get("fix_guidance"),
                            category=result.get("category"),
                            change_snippet=review_unit.change_snippet,
                            line_no=review_unit.default_line_no,
                            candidate_line_nos=review_unit.candidate_line_nos,
                        )
                        if not draft.should_publish:
                            continue
                        target_line_no = self._resolve_target_line_no(
                            requested_line_no=draft.line_no,
                            review_unit=review_unit,
                            result=result,
                        )
                        if self._requires_precise_anchor(
                            review_unit=review_unit,
                            result=result,
                        ) and (target_line_no is None):
                            continue
                        human_key = self._human_key(
                            file_path=file_item["path"],
                            line_no=target_line_no,
                            draft=draft,
                        )
                        if human_key in seen_human_keys:
                            continue

                        issue_signature = self._issue_signature(result, review_unit)
                        fingerprint = self._fingerprint(
                            pr_id=pr_id,
                            file_path=file_item["path"],
                            line_no=target_line_no,
                            human_key=human_key,
                            issue_signature=issue_signature,
                        )
                        if fingerprint in existing_fingerprints:
                            continue
                        existing_fingerprints.add(fingerprint)
                        seen_fingerprints.add(fingerprint)

                        seen_human_keys.add(human_key)
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
                            status="open",
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
            refreshed = session.get(ReviewRun, review_run_id)
            if refreshed is not None:
                review_run = refreshed
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
            .limit(max(self.settings.batch_size * 10, 50))
            .all()
        )
        unpublished = self._select_batch_findings(unpublished)
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
            finding.summary,
        ]
        if finding.suggested_fix:
            lines.extend(
                [
                    "",
                    "권장 수정",
                    finding.suggested_fix,
                ]
            )
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
        return int(match.group("new"))

    def _iter_review_units(self, patch: str) -> list[ReviewUnit]:
        lines = patch.splitlines()
        units: list[ReviewUnit] = []
        current_header: str | None = None
        current_lines: list[str] = []

        for line in lines:
            if line.startswith("@@"):
                if current_header is not None:
                    units.append(self._build_review_unit(current_header, current_lines))
                current_header = line
                current_lines = []
                continue
            if current_header is not None:
                current_lines.append(line)

        if current_header is not None:
            units.append(self._build_review_unit(current_header, current_lines))

        if units:
            expanded: list[ReviewUnit] = []
            for unit in units:
                expanded.extend(self._split_large_added_unit(unit))
            return expanded
        return [
            ReviewUnit(
                patch=patch,
                change_snippet=patch,
                default_line_no=self._extract_line_no(patch),
                candidate_line_nos=(),
                changed_lines=(),
            )
        ]

    def _build_review_unit(self, header: str, hunk_lines: list[str]) -> ReviewUnit:
        match = HUNK_RE.match(header)
        old_line_no = int(match.group("old")) if match else None
        new_line_no = int(match.group("new")) if match else None
        changed_lines: list[ChangedPatchLine] = []
        candidate_line_nos: list[int] = []
        numbered_lines: list[str] = [header]

        for raw_line in hunk_lines:
            if raw_line.startswith("\\"):
                continue
            if raw_line.startswith("+") and not raw_line.startswith("+++"):
                changed_lines.append(
                    ChangedPatchLine(marker="+", text=raw_line[1:], new_line_no=new_line_no)
                )
                if new_line_no is not None:
                    candidate_line_nos.append(new_line_no)
                    numbered_lines.append(f"L{new_line_no} | + {raw_line[1:]}")
                    new_line_no += 1
                continue
            if raw_line.startswith("-") and not raw_line.startswith("---"):
                changed_lines.append(
                    ChangedPatchLine(marker="-", text=raw_line[1:], old_line_no=old_line_no)
                )
                if old_line_no is not None:
                    numbered_lines.append(f"OLD{old_line_no} | - {raw_line[1:]}")
                    old_line_no += 1
                continue
            if raw_line.startswith(" "):
                if old_line_no is not None:
                    old_line_no += 1
                if new_line_no is not None:
                    new_line_no += 1

        normalized_candidates = tuple(dict.fromkeys(candidate_line_nos))
        if normalized_candidates:
            default_line_no = normalized_candidates[0]
        else:
            default_line_no = self._extract_line_no(header)
        return ReviewUnit(
            patch="\n".join([header, *hunk_lines]),
            change_snippet="\n".join(numbered_lines),
            default_line_no=default_line_no,
            candidate_line_nos=normalized_candidates,
            changed_lines=tuple(changed_lines),
        )

    def _split_large_added_unit(self, unit: ReviewUnit) -> list[ReviewUnit]:
        if len(unit.candidate_line_nos) <= MAX_LINES_PER_REVIEW_UNIT:
            return [unit]
        if not unit.changed_lines or any(line.marker != "+" for line in unit.changed_lines):
            return [unit]

        added_lines = [line for line in unit.changed_lines if line.new_line_no is not None]
        if len(added_lines) <= MAX_LINES_PER_REVIEW_UNIT:
            return [unit]

        split_units: list[ReviewUnit] = []
        for start in range(0, len(added_lines), MAX_LINES_PER_REVIEW_UNIT):
            chunk = added_lines[start : start + MAX_LINES_PER_REVIEW_UNIT]
            first_line_no = chunk[0].new_line_no
            if first_line_no is None:
                continue

            header = f"@@ -0,0 +{first_line_no},{len(chunk)} @@"
            patch_lines = [header, *[f"+{line.text}" for line in chunk]]
            numbered_lines = [header, *[f"L{line.new_line_no} | + {line.text}" for line in chunk]]
            candidate_line_nos = tuple(
                line.new_line_no for line in chunk if line.new_line_no is not None
            )
            split_units.append(
                ReviewUnit(
                    patch="\n".join(patch_lines),
                    change_snippet="\n".join(numbered_lines),
                    default_line_no=candidate_line_nos[0] if candidate_line_nos else first_line_no,
                    candidate_line_nos=candidate_line_nos,
                    changed_lines=tuple(chunk),
                )
            )

        return split_units or [unit]

    def _issue_signature(self, result: dict[str, object], review_unit: ReviewUnit) -> str:
        changed_lines = [
            line.text.strip() for line in review_unit.changed_lines if line.text.strip()
        ]
        signature_source = " ".join(changed_lines[:3]) or review_unit.patch
        signature_source += f"|{result['rule_no']}|{result['title']}|{result['summary']}"
        return hashlib.sha1(signature_source.encode("utf-8")).hexdigest()[:12]

    def _resolve_target_line_no(
        self,
        *,
        requested_line_no: int | None,
        review_unit: ReviewUnit,
        result: dict[str, object],
    ) -> int | None:
        if (
            requested_line_no is not None
            and requested_line_no in review_unit.candidate_line_nos
        ):
            return requested_line_no

        issue = classify_issue(
            extract_changed_excerpt(review_unit.change_snippet),
            result.get("category"),
            str(result.get("title") or ""),
            str(result.get("summary") or ""),
        )
        inferred_line = select_candidate_line(
            change_snippet=review_unit.change_snippet,
            candidate_line_nos=review_unit.candidate_line_nos,
            issue=issue,
        )
        if inferred_line is not None:
            return inferred_line
        if requires_direct_signal(issue):
            return None
        if review_unit.default_line_no in review_unit.candidate_line_nos:
            return review_unit.default_line_no
        if review_unit.candidate_line_nos:
            return review_unit.candidate_line_nos[0]
        return requested_line_no or review_unit.default_line_no

    def _requires_precise_anchor(
        self,
        *,
        review_unit: ReviewUnit,
        result: dict[str, object],
    ) -> bool:
        issue = classify_issue(
            extract_changed_excerpt(review_unit.change_snippet),
            result.get("category"),
            str(result.get("title") or ""),
            str(result.get("summary") or ""),
        )
        return requires_direct_signal(issue)

    def _fingerprint(
        self,
        *,
        pr_id: int,
        file_path: str,
        line_no: int | None,
        human_key: str,
        issue_signature: str,
    ) -> str:
        normalized_line = line_no or 0
        return f"pr{pr_id}:{file_path}:{normalized_line}:{human_key}:{issue_signature}"

    def _human_key(
        self,
        *,
        file_path: str,
        line_no: int | None,
        draft: object,
    ) -> str:
        normalized_line = (line_no or 0) // 64
        title = getattr(draft, "title", "")
        summary = getattr(draft, "summary", "")
        source = f"{file_path}|{normalized_line}|{title}|{summary}"
        return hashlib.sha1(source.encode()).hexdigest()[:12]

    def _safe_post_status(self, pr_id: int, *, state: str, description: str) -> None:
        try:
            self.platform_client.post_status(pr_id, state=state, description=description)
        except Exception:
            return

    def _select_batch_findings(self, findings: list[ReviewFinding]) -> list[ReviewFinding]:
        selected: list[ReviewFinding] = []
        seen_file_titles: set[tuple[str, str]] = set()
        title_counts: dict[str, int] = {}

        for finding in findings:
            file_title = (finding.file_path, finding.title)
            if file_title in seen_file_titles:
                continue
            if title_counts.get(finding.title, 0) >= 2:
                continue

            selected.append(finding)
            seen_file_titles.add(file_title)
            title_counts[finding.title] = title_counts.get(finding.title, 0) + 1
            if len(selected) >= self.settings.batch_size:
                break

        return selected

    def _load_existing_fingerprints(self, session: Session, pr_id: int) -> set[str]:
        rows = (
            session.query(ReviewFinding.fingerprint)
            .filter(
                ReviewFinding.pr_id == pr_id,
                ReviewFinding.status.in_(["open", "published", "failed_publication"]),
            )
            .all()
        )
        return {fingerprint for (fingerprint,) in rows}
