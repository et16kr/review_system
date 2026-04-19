from __future__ import annotations

import re
from collections import Counter

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "then",
    "this",
    "to",
    "use",
    "with",
}

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_:+.-]*")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def split_sentences(value: str) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def summarize_text(value: str, max_sentences: int = 2, max_chars: int = 260) -> str:
    sentences = split_sentences(value)
    if not sentences:
        return ""
    summary = " ".join(sentences[:max_sentences]).strip()
    if len(summary) <= max_chars:
        return summary
    return summary[: max_chars - 3].rstrip() + "..."


def tokenize(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(value)]


def extract_keywords(value: str, limit: int = 12) -> list[str]:
    tokens = [token for token in tokenize(value) if token not in STOPWORDS and len(token) > 2]
    counts = Counter(tokens)
    return [token for token, _ in counts.most_common(limit)]

