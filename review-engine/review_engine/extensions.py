from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

from review_engine.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtensionSpec:
    name: str = "extension"
    rule_roots: tuple[Path, ...] = ()
    prompt_roots: tuple[Path, ...] = ()
    detectors: tuple[Any, ...] = ()


def discover_extension_specs(settings: Settings) -> list[ExtensionSpec]:
    specs: list[ExtensionSpec] = []
    if settings.extension_rule_roots or settings.extension_prompt_roots:
        specs.append(
            ExtensionSpec(
                name="filesystem",
                rule_roots=tuple(settings.extension_rule_roots),
                prompt_roots=tuple(settings.extension_prompt_roots),
            )
        )

    for entry_point in entry_points(group=settings.extension_entry_point_group):
        payload = _load_extension_entry_point_payload(entry_point)
        if payload is None:
            continue

        try:
            specs.extend(_normalize_specs(payload, fallback_name=entry_point.name))
        except Exception as exc:
            if settings.strict_extension_loading:
                raise ValueError(
                    f"Invalid rule extension spec from entry point {entry_point.name}: {exc}"
                ) from exc
            logger.warning("Ignoring invalid extension spec from %s: %s", entry_point.name, exc)
    return specs


def _normalize_specs(payload: Any, *, fallback_name: str) -> list[ExtensionSpec]:
    if isinstance(payload, ExtensionSpec):
        return [payload]
    if isinstance(payload, list | tuple):
        specs: list[ExtensionSpec] = []
        for item in payload:
            specs.extend(_normalize_specs(item, fallback_name=fallback_name))
        return specs
    if isinstance(payload, dict):
        return [
            ExtensionSpec(
                name=str(payload.get("name") or fallback_name),
                rule_roots=_coerce_paths(payload.get("rule_roots", ())),
                prompt_roots=_coerce_paths(payload.get("prompt_roots", ())),
                detectors=tuple(payload.get("detectors", ())),
            )
        ]
    raise TypeError(f"Unsupported extension payload type: {type(payload)!r}")


def _coerce_paths(items: Any) -> tuple[Path, ...]:
    if isinstance(items, (str, Path)):
        items = [items]
    return tuple(Path(item).expanduser().resolve() for item in items)


def _load_extension_entry_point_payload(entry_point: Any) -> Any | None:
    # Optional detector and prompt plugins are allowed to fail independently
    # from the core rule-data path. Strict mode is enforced after rule roots are
    # discovered and validated, not during optional entry-point import.
    try:
        loaded = entry_point.load()
    except Exception as exc:
        logger.warning(
            "Failed to import rule extension entry point %s: %s",
            entry_point.name,
            exc,
        )
        return None

    try:
        return loaded() if callable(loaded) else loaded
    except Exception as exc:
        logger.warning(
            "Failed to initialize rule extension entry point %s: %s",
            entry_point.name,
            exc,
        )
        return None
