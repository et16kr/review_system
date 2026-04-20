from __future__ import annotations

import re
from collections.abc import Iterable

from bs4 import BeautifulSoup, Tag

from review_engine.models import ParsedRule
from review_engine.text_utils import clean_text, extract_keywords, summarize_text

RULE_HEADING_RE = re.compile(
    r"^(?P<rule_no>[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z0-9]+)+):\s*(?P<title>.+)$"
)


def parse_cpp_core_guidelines(html: str, source: str) -> list[ParsedRule]:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body or soup
    current_section = "General"
    records: list[ParsedRule] = []

    for tag in body.find_all(["h1", "h3"]):
        text = clean_text(tag.get_text(" ", strip=True))
        if tag.name == "h1":
            current_section = text
            continue

        match = RULE_HEADING_RE.match(text)
        if not match:
            continue

        text_blocks = list(_iter_rule_blocks(tag))
        combined_text = "\n".join(text_blocks).strip()
        summary = summarize_text(combined_text) or match.group("title")
        keyword_basis = f"{match.group('rule_no')} {match.group('title')} {combined_text}"
        records.append(
            ParsedRule(
                rule_no=match.group("rule_no"),
                source=source,
                source_family="cpp_core",
                section=match.group("rule_no").split(".")[0] or current_section,
                title=clean_text(match.group("title")),
                text=combined_text,
                summary=summary,
                keywords=extract_keywords(keyword_basis),
            )
        )

    return records


def _iter_rule_blocks(tag: Tag) -> Iterable[str]:
    for sibling in tag.next_siblings:
        if not isinstance(sibling, Tag):
            continue
        if sibling.name in {"h1", "h2", "h3"}:
            break
        snippet = clean_text(sibling.get_text(" ", strip=True))
        if snippet:
            yield snippet
