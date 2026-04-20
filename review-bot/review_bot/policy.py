from __future__ import annotations

import json
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path


@dataclass(frozen=True)
class PathPolicy:
    glob: str
    score_adjustment: float = 0.0
    minimum_score: float | None = None
    suppress_rules: frozenset[str] = frozenset()
    promote_rules: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ReviewPolicy:
    path_policies: tuple[PathPolicy, ...] = ()
    allowed_rules: frozenset[str] = frozenset()
    suppressed_rules: frozenset[str] = frozenset()

    def rules_for_path(self, file_path: str) -> tuple[PathPolicy, ...]:
        return tuple(policy for policy in self.path_policies if fnmatch(file_path, policy.glob))


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
