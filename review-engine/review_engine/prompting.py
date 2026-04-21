from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from review_engine.config import Settings, get_settings
from review_engine.extensions import discover_extension_specs


class PromptComposer:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
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
        roots: list[Path] = []
        if self.settings.prompt_root is not None:
            roots.append(self.settings.prompt_root)
        roots.extend(self.settings.extension_prompt_roots)
        for spec in discover_extension_specs(self.settings):
            roots.extend(spec.prompt_roots)
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


@lru_cache(maxsize=1)
def get_prompt_composer() -> PromptComposer:
    return PromptComposer()
