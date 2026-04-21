from __future__ import annotations

import os
import logging
from functools import lru_cache
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _split_path_env(name: str) -> list[Path]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return []
    return [
        Path(item).expanduser().resolve()
        for item in raw.split(os.pathsep)
        if item.strip()
    ]


class PromptComposer:
    def __init__(self) -> None:
        self._roots = self._build_roots()

    def compose(
        self,
        *,
        language_id: str = "cpp",
        profile_id: str = "default",
        overlay_refs: list[str] | None = None,
    ) -> str:
        pieces: list[str] = []
        for relative in (
            Path("base/system.md"),
            Path("languages") / f"{language_id}.md",
            Path("profiles") / f"{profile_id}.md",
        ):
            content = self._load_first(relative)
            if content:
                pieces.append(content)

        for ref in overlay_refs or []:
            content = self._load_overlay(ref)
            if content:
                pieces.append(content)
        return "\n\n".join(piece.strip() for piece in pieces if piece.strip()).strip()

    def _build_roots(self) -> list[Path]:
        project_root = Path(__file__).resolve().parents[2]
        default_root = project_root.parent / "review-engine" / "prompts"
        roots: list[Path] = [
            Path(os.getenv("REVIEW_ENGINE_PROMPT_ROOT", default_root)).expanduser().resolve()
        ]
        roots.extend(_split_path_env("REVIEW_ENGINE_EXTENSION_PROMPT_ROOTS"))
        roots.extend(_entry_point_prompt_roots())
        return roots

    def _load_overlay(self, ref: str) -> str:
        candidates = [
            Path(ref),
            Path("profiles") / f"{ref}.md",
            Path("overlays") / f"{ref}.md",
        ]
        for candidate in candidates:
            content = self._load_first(candidate)
            if content:
                return content
        return ""

    def _load_first(self, relative: Path) -> str:
        for root in self._roots:
            path = root / relative
            if path.exists():
                return path.read_text(encoding="utf-8").strip()
        return ""


def _entry_point_prompt_roots() -> list[Path]:
    roots: list[Path] = []
    for entry_point in entry_points(group="review_engine.rule_extensions"):
        try:
            loaded = entry_point.load()
            payload = loaded() if callable(loaded) else loaded
            roots.extend(_coerce_prompt_roots(payload))
        except Exception as exc:
            logger.warning("Failed to load prompt extension entry point %s: %s", entry_point.name, exc)
            continue
    return roots


def _coerce_prompt_roots(payload: Any) -> list[Path]:
    if isinstance(payload, dict):
        items = payload.get("prompt_roots", [])
        return _coerce_paths(items)
    if isinstance(payload, list | tuple):
        roots: list[Path] = []
        for item in payload:
            roots.extend(_coerce_prompt_roots(item))
        return roots
    if hasattr(payload, "prompt_roots"):
        return _coerce_paths(getattr(payload, "prompt_roots"))
    return []


def _coerce_paths(items: Any) -> list[Path]:
    if isinstance(items, (str, Path)):
        items = [items]
    return [Path(item).expanduser().resolve() for item in items]


@lru_cache(maxsize=1)
def get_prompt_composer() -> PromptComposer:
    return PromptComposer()
