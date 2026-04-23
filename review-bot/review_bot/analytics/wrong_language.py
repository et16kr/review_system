from __future__ import annotations

from pathlib import Path
from typing import Literal

WrongLanguageProvenance = Literal["smoke", "production", "unknown"]
WrongLanguageCause = Literal[
    "synthetic_smoke",
    "detector_miss",
    "wrong_thread_target",
    "policy_mismatch",
    "needs_inspection",
]
WrongLanguageActionability = Literal[
    "ignore_for_detector_backlog",
    "inspect_thread",
    "update_policy_or_fixture",
    "fix_detector",
]

SMOKE_PROJECT_REFS = frozenset(
    {
        "root/review-system-multilang-smoke",
        "root/review-system-curated-polyglot-smoke",
        "root/review-system-cuda-smoke",
    }
)
SMOKE_BODY_PHRASES = (
    "telemetry 점검",
    "문서 예외 흐름 점검용",
    "오분류 telemetry",
    "YAML 스레드 오분류 telemetry",
)

_DOCS_EXTENSIONS = {".md", ".mdx", ".markdown", ".rst", ".adoc"}
_DOCS_FILENAMES = {
    "readme",
    "readme.md",
    "changelog",
    "changelog.md",
    "contributing",
    "contributing.md",
    "security.md",
    "code_of_conduct.md",
}
_LANGUAGE_EXTENSIONS = {
    "markdown": _DOCS_EXTENSIONS,
    "yaml": {".yml", ".yaml"},
    "dockerfile": {".dockerfile"},
    "sql": {".sql"},
    "python": {".py", ".pyi"},
    "typescript": {".ts", ".tsx"},
    "javascript": {".js", ".jsx", ".mjs", ".cjs"},
    "java": {".java"},
    "go": {".go"},
    "rust": {".rs"},
    "bash": {".sh", ".bash", ".zsh"},
    "c": {".c", ".h"},
    "cpp": {".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"},
    "cuda": {".cu", ".cuh"},
}
_LANGUAGE_CONTEXTS = {
    "yaml": {"github_actions", "gitlab_ci", "kubernetes", "product_config"},
    "sql": {"analytics", "migration_sql"},
    "typescript": {"app_router", "nextjs_frontend"},
    "cuda": {
        "cuda_async_runtime",
        "cuda_pipeline_async",
        "cuda_thread_block_cluster",
        "cuda_tma",
        "cuda_wgmma",
        "cuda_multigpu",
        "cuda_tensor_core",
        "cuda_cooperative_groups",
    },
}
_LANGUAGE_PATH_PREFIXES = {
    "markdown": {"docs", "documentation", "wiki"},
    "yaml": {"deploy", "deployment", "k8s", "kubernetes", ".github", "config", "configs"},
    "sql": {"db", "database", "migrations", "warehouse"},
    "typescript": {"app", "pages"},
    "javascript": {"app", "pages"},
    "cuda": {"kernels", "distributed"},
}


def classify_wrong_language_provenance(
    project_ref: str | None,
    body: str | None,
) -> WrongLanguageProvenance:
    normalized_project_ref = str(project_ref or "").strip()
    normalized_body = str(body or "")
    if normalized_project_ref in SMOKE_PROJECT_REFS or any(
        phrase in normalized_body for phrase in SMOKE_BODY_PHRASES
    ):
        return "smoke"
    if normalized_project_ref:
        return "production"
    return "unknown"


def classify_wrong_language_cause(
    *,
    detected_language_id: str,
    expected_language_id: str,
    profile_id: str | None,
    context_id: str | None,
    file_path: str,
    provenance: WrongLanguageProvenance,
) -> WrongLanguageCause:
    detected = _normalize_language_id(detected_language_id)
    expected = _normalize_language_id(expected_language_id)
    if provenance == "smoke":
        return "synthetic_smoke"
    if detected == "unknown" or expected == "unknown":
        return "needs_inspection"
    if detected == expected:
        return "needs_inspection"

    expected_fits = _language_fits_path_or_context(expected, file_path, profile_id, context_id)
    detected_fits = _language_fits_path_or_context(detected, file_path, profile_id, context_id)

    if expected == "markdown" and _is_docs_path(file_path):
        return "detector_miss"
    if expected == "markdown" and detected_fits and not _is_docs_path(file_path):
        return "wrong_thread_target"
    if expected_fits and not detected_fits:
        return "detector_miss"
    if detected_fits and not expected_fits and expected in {"markdown", "text", "plain_text"}:
        return "wrong_thread_target"
    if detected_fits and not expected_fits:
        return "policy_mismatch"
    return "needs_inspection"


def wrong_language_actionability(
    triage_cause: WrongLanguageCause,
) -> WrongLanguageActionability:
    if triage_cause == "synthetic_smoke":
        return "ignore_for_detector_backlog"
    if triage_cause == "detector_miss":
        return "fix_detector"
    if triage_cause == "policy_mismatch":
        return "update_policy_or_fixture"
    return "inspect_thread"


def _normalize_language_id(language_id: str | None) -> str:
    return str(language_id or "unknown").strip().lower().replace("-", "_") or "unknown"


def _normalize_path(file_path: str) -> tuple[str, list[str], str, str]:
    normalized = str(file_path or "").replace("\\", "/").strip("/")
    parts = [part for part in normalized.split("/") if part]
    name = Path(normalized).name.lower()
    suffix = Path(normalized).suffix.lower()
    return normalized.lower(), parts, name, suffix


def _is_docs_path(file_path: str) -> bool:
    _normalized, parts, name, suffix = _normalize_path(file_path)
    return bool(
        suffix in _DOCS_EXTENSIONS
        or name in _DOCS_FILENAMES
        or (parts and parts[0].lower() in _LANGUAGE_PATH_PREFIXES["markdown"])
    )


def _language_fits_path_or_context(
    language_id: str,
    file_path: str,
    profile_id: str | None,
    context_id: str | None,
) -> bool:
    normalized, parts, name, suffix = _normalize_path(file_path)
    if language_id == "markdown" and _is_docs_path(file_path):
        return True
    if suffix in _LANGUAGE_EXTENSIONS.get(language_id, set()):
        return True
    if language_id == "dockerfile" and name == "dockerfile":
        return True
    if language_id == "yaml" and name in {".gitlab-ci.yml", ".gitlab-ci.yaml"}:
        return True
    if language_id == "yaml" and normalized.startswith(".github/workflows/"):
        return True
    if parts and parts[0].lower() in _LANGUAGE_PATH_PREFIXES.get(language_id, set()):
        return True
    if str(context_id or "") in _LANGUAGE_CONTEXTS.get(language_id, set()):
        return True
    if str(profile_id or "") in _LANGUAGE_CONTEXTS.get(language_id, set()):
        return True
    return False
