from __future__ import annotations

import re
from dataclasses import dataclass, field

from review_engine.models import QueryPattern
from review_engine.query.languages.common import deduplicate_patterns, matching_lines


@dataclass(frozen=True)
class PatternSpec:
    name: str
    pattern: str
    description: str
    weight: float

    def compile(self) -> re.Pattern[str]:
        return re.compile(self.pattern, re.MULTILINE)


@dataclass
class LanguageQueryPlugin:
    plugin_id: str
    display_name: str
    default_focus: str
    pattern_specs: tuple[PatternSpec, ...] = ()
    hinted_rules: dict[str, tuple[str, ...]] = field(default_factory=dict)
    direct_hint_patterns: set[str] = field(default_factory=set)

    def analyze(self, source_text: str) -> list[QueryPattern]:
        patterns: list[QueryPattern] = []
        for spec in self.pattern_specs:
            regex = spec.compile()
            if not regex.search(source_text):
                continue
            patterns.append(
                QueryPattern(
                    name=spec.name,
                    description=spec.description,
                    weight=spec.weight,
                    evidence=matching_lines(source_text, regex),
                )
            )
        return deduplicate_patterns(patterns)

    def build_query_text(
        self,
        *,
        input_kind: str,
        patterns: list[QueryPattern],
        profile_id: str,
        context_id: str | None,
        dialect_id: str | None,
    ) -> str:
        context_bits = [self.display_name]
        if context_id:
            context_bits.append(context_id.replace("_", " "))
        if dialect_id and dialect_id != "generic":
            context_bits.append(dialect_id.replace("_", " "))
        subject = " / ".join(context_bits)
        if patterns:
            concerns = " ".join(pattern.description for pattern in patterns)
            return (
                f"Review this {subject} {input_kind} using the {profile_id} profile. "
                f"Focus on the following likely issues. {concerns}"
            )
        return (
            f"Review this {subject} {input_kind} using the {profile_id} profile. "
            f"Focus on {self.default_focus}."
        )

    def collect_hinted_rules(self, patterns: list[QueryPattern], *, direct_only: bool = False) -> set[str]:
        hinted_rules: set[str] = set()
        for pattern in patterns:
            if direct_only and pattern.name not in self.direct_hint_patterns:
                continue
            hinted_rules.update(self.hinted_rules.get(pattern.name, ()))
        return hinted_rules
