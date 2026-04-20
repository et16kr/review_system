from __future__ import annotations

import json
from dataclasses import dataclass
from fnmatch import fnmatch
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class PathPolicy:
    glob: str
    score_adjustment: float = 0.0
    minimum_score: float | None = None
    suppress_rules: frozenset[str] = frozenset()
    promote_rules: frozenset[str] = frozenset()


@lru_cache(maxsize=512)
def _match_path_policies(
    path_policies: tuple[PathPolicy, ...], file_path: str
) -> tuple[PathPolicy, ...]:
    """경로별 정책 매칭 결과를 캐싱한다 (O(n*m) → O(1) 반복 호출)."""
    return tuple(p for p in path_policies if fnmatch(file_path, p.glob))


@dataclass(frozen=True)
class ReviewPolicy:
    path_policies: tuple[PathPolicy, ...] = ()
    allowed_rules: frozenset[str] = frozenset()
    suppressed_rules: frozenset[str] = frozenset()

    def rules_for_path(self, file_path: str) -> tuple[PathPolicy, ...]:
        return _match_path_policies(self.path_policies, file_path)


def load_review_policy(path: str | None) -> ReviewPolicy:
    if not path:
        return ReviewPolicy()
    policy_path = Path(path)
    if not policy_path.exists():
        return ReviewPolicy()
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    path_policies = tuple(
        PathPolicy(
            glob=str(item["glob"]),
            score_adjustment=float(item.get("score_adjustment", 0.0)),
            minimum_score=(
                float(item["minimum_score"]) if item.get("minimum_score") is not None else None
            ),
            suppress_rules=frozenset(str(rule) for rule in item.get("suppress_rules", [])),
            promote_rules=frozenset(str(rule) for rule in item.get("promote_rules", [])),
        )
        for item in payload.get("path_policies", [])
        if item.get("glob")
    )
    return ReviewPolicy(
        path_policies=path_policies,
        allowed_rules=frozenset(str(rule) for rule in payload.get("allowed_rules", [])),
        suppressed_rules=frozenset(str(rule) for rule in payload.get("suppressed_rules", [])),
    )
