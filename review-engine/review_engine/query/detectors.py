from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from review_engine.config import Settings, get_settings
from review_engine.extensions import discover_extension_specs
from review_engine.models import QueryPattern
from review_engine.query.languages import BUILTIN_QUERY_PLUGINS
from review_engine.query.languages.common import deduplicate_patterns

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
class BuiltinLanguageDetector:
    plugin_id: str

    def supports(self, *, language_id: str, profile_id: str | None) -> bool:
        del language_id, profile_id
        return True

    def analyze(
        self,
        *,
        file_path: str | None,
        file_context: str | None,
        diff: str | None,
        code: str | None,
    ) -> list[QueryPattern]:
        del file_path, file_context
        plugin = BUILTIN_QUERY_PLUGINS[self.plugin_id]
        source_text = code if code is not None else diff or ""
        return plugin.analyze(source_text)


class QueryDetectorManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._extension_plugins = self._load_extension_plugins()

    def analyze(
        self,
        *,
        language_id: str,
        profile_id: str,
        query_plugin_id: str,
        detector_refs: list[str] | None,
        include_shared_detector: bool = True,
        file_path: str | None,
        file_context: str | None,
        diff: str | None,
        code: str | None,
    ) -> list[QueryPattern]:
        patterns: list[QueryPattern] = []
        allowed = set(detector_refs or [])
        builtin = BuiltinLanguageDetector(query_plugin_id)
        patterns.extend(
            builtin.analyze(
                file_path=file_path,
                file_context=file_context,
                diff=diff,
                code=code,
            )
        )
        if include_shared_detector and query_plugin_id != "shared":
            patterns.extend(
                BuiltinLanguageDetector("shared").analyze(
                    file_path=file_path,
                    file_context=file_context,
                    diff=diff,
                    code=code,
                )
            )
        for plugin in self._extension_plugins:
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
        return deduplicate_patterns(patterns)

    def build_query_text(
        self,
        *,
        query_plugin_id: str,
        input_kind: str,
        patterns: list[QueryPattern],
        profile_id: str,
        context_id: str | None,
        dialect_id: str | None,
    ) -> str:
        plugin = BUILTIN_QUERY_PLUGINS[query_plugin_id]
        return plugin.build_query_text(
            input_kind=input_kind,
            patterns=patterns,
            profile_id=profile_id,
            context_id=context_id,
            dialect_id=dialect_id,
        )

    def collect_hinted_rules(
        self,
        *,
        query_plugin_id: str,
        patterns: list[QueryPattern],
        direct_only: bool = False,
    ) -> set[str]:
        plugin = BUILTIN_QUERY_PLUGINS[query_plugin_id]
        return plugin.collect_hinted_rules(patterns, direct_only=direct_only)

    def _load_extension_plugins(self) -> list[QueryDetectorPlugin]:
        plugins: list[QueryDetectorPlugin] = []
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
