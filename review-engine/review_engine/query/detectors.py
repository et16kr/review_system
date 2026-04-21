from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from review_engine.config import Settings, get_settings
from review_engine.extensions import discover_extension_specs
from review_engine.models import QueryPattern
from review_engine.query.cpp_feature_extractor import extract_query_patterns

logger = logging.getLogger(__name__)


class QueryDetectorPlugin(Protocol):
    plugin_id: str

    def supports(self, *, language_id: str, profile_id: str | None) -> bool: ...

    def analyze(
        self,
        *,
        file_path: str | None,
        file_context: str | None,
        diff: str | None,
        code: str | None,
    ) -> list[QueryPattern]: ...


@dataclass
class CppPatternDetector:
    plugin_id: str = "builtin:cpp"

    def supports(self, *, language_id: str, profile_id: str | None) -> bool:
        del profile_id
        return language_id == "cpp"

    def analyze(
        self,
        *,
        file_path: str | None,
        file_context: str | None,
        diff: str | None,
        code: str | None,
    ) -> list[QueryPattern]:
        del file_path, file_context
        source_text = code if code is not None else diff or ""
        return extract_query_patterns(source_text)


class QueryDetectorManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._plugins = self._load_plugins()

    def analyze(
        self,
        *,
        language_id: str,
        profile_id: str,
        detector_refs: list[str] | None,
        file_path: str | None,
        file_context: str | None,
        diff: str | None,
        code: str | None,
    ) -> list[QueryPattern]:
        patterns: list[QueryPattern] = []
        allowed = set(detector_refs or [])
        for plugin in self._plugins:
            if allowed and plugin.plugin_id not in allowed:
                continue
            if not plugin.supports(language_id=language_id, profile_id=profile_id):
                continue
            try:
                patterns.extend(
                    plugin.analyze(
                        file_path=file_path,
                        file_context=file_context,
                        diff=diff,
                        code=code,
                    )
                )
            except Exception as exc:
                logger.warning("Detector plugin %s failed: %s", plugin.plugin_id, exc)
        return _deduplicate_patterns(patterns)

    def _load_plugins(self) -> list[QueryDetectorPlugin]:
        plugins: list[QueryDetectorPlugin] = [CppPatternDetector()]
        for spec in discover_extension_specs(self.settings):
            for item in spec.detectors:
                plugin = _resolve_plugin(item)
                if plugin is not None:
                    plugins.append(plugin)
        return plugins


def _resolve_plugin(item: Any) -> QueryDetectorPlugin | None:
    candidate = item() if callable(item) else item
    if all(hasattr(candidate, field) for field in ("plugin_id", "supports", "analyze")):
        return candidate
    logger.warning("Ignoring invalid detector plugin payload: %r", item)
    return None


def _deduplicate_patterns(patterns: list[QueryPattern]) -> list[QueryPattern]:
    deduped: dict[str, QueryPattern] = {}
    for pattern in patterns:
        existing = deduped.get(pattern.name)
        if existing is None or pattern.weight > existing.weight:
            deduped[pattern.name] = pattern
    return list(deduped.values())
