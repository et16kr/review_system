from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any, TypeVar

import yaml
from pydantic import ValidationError

from review_engine.models import (
    PriorityPolicy,
    ProfileConfig,
    RulePackageManifest,
    RulePackManifest,
    RuleRootManifest,
    RuleSourceManifest,
    StrictAuthoringModel,
)

PACKAGE_MANIFEST_NAME = "package.yaml"
DEFAULT_PRIVATE_ARTIFACT_ROOT = Path("/tmp/review-engine-private-rule-packages")
MAX_PRIVATE_COLLECTION_PREFIX_LENGTH = 48

_ModelT = TypeVar("_ModelT", bound=StrictAuthoringModel)
_COLLECTION_COMPONENT_RE = re.compile(r"[^A-Za-z0-9_-]+")


class RulePackageValidationError(ValueError):
    pass


def validate_rule_package(
    package_root: Path,
    *,
    manifest_name: str = PACKAGE_MANIFEST_NAME,
) -> dict[str, Any]:
    resolved_package_root = package_root.expanduser().resolve()
    package_manifest_path = _resolve_package_relative_path(
        package_root=resolved_package_root,
        relative_path=manifest_name,
        field_name="manifest_name",
        allow_root=False,
    )
    if package_manifest_path.parent != resolved_package_root:
        raise RulePackageValidationError(
            f"manifest_name must be a file in the package root: {manifest_name}"
        )
    package_manifest = _load_model(
        package_manifest_path,
        RulePackageManifest,
        label="package manifest",
    )

    extension_roots = [
        _validate_extension_root(
            package_root=resolved_package_root,
            relative_path=relative_path,
        )
        for relative_path in package_manifest.extension_roots
    ]
    included = _validate_included_files(
        package_root=resolved_package_root,
        manifest=package_manifest,
        extension_roots=extension_roots,
    )
    provenance = _validate_provenance(
        package_root=resolved_package_root,
        manifest=package_manifest,
    )

    return {
        "source_of_truth": "package_yaml",
        "validation_mode": "read_only",
        "package_root": str(resolved_package_root),
        "package_manifest_path": str(package_manifest_path),
        "package_id": package_manifest.package_id,
        "package_version": package_manifest.package_version,
        "package_kind": package_manifest.package_kind,
        "schema_version": package_manifest.schema_version,
        "compatible_review_engine": package_manifest.compatible_review_engine.model_dump(),
        "extension_roots": extension_roots,
        "included": included,
        "provenance": provenance,
        "mutated_files": [],
    }


def _package_artifact_root(
    *,
    package_id: str,
    package_version: str,
    private_artifact_root: Path | None,
) -> Path:
    base_root = (private_artifact_root or DEFAULT_PRIVATE_ARTIFACT_ROOT).expanduser().resolve()
    return base_root / package_id / package_version / "validation"


def _private_collection_prefix(package_id: str, package_version: str) -> str:
    package_component = _sanitize_collection_component(package_id)
    version_component = _sanitize_collection_component(package_version)
    prefix = f"pkg_guidelines_{package_component}_{version_component}"
    if len(prefix) <= MAX_PRIVATE_COLLECTION_PREFIX_LENGTH:
        return prefix

    digest = hashlib.sha256(f"{package_id}:{package_version}".encode("utf-8")).hexdigest()[:12]
    truncated = package_component[:24].rstrip("_")
    return f"pkg_guidelines_{truncated}_{digest}"


def _sanitize_collection_component(value: str) -> str:
    sanitized = _COLLECTION_COMPONENT_RE.sub("_", value).strip("_")
    return sanitized or "package"


def _records_from_root(records: list[Any], root: Path) -> list[Any]:
    resolved_root = root.resolve()
    return [
        record
        for record in records
        if _is_relative_to(Path(record.source).resolve(), resolved_root)
    ]


def _validate_private_artifact_boundary(
    *,
    base_settings: Any,
    private_settings: Any,
    ingest_summary: dict[str, Any],
) -> dict[str, Any]:
    public_data_dir = (base_settings.project_root / "data").resolve()
    dataset_paths = sorted(
        {
            path
            for per_language in ingest_summary.get("dataset_paths", {}).values()
            for path in per_language.values()
        }
    )
    collection_names = sorted(ingest_summary.get("collections", {}))
    language_ids = sorted(ingest_summary.get("languages", {})) or [
        private_settings.default_language_id
    ]
    public_collection_names = sorted(
        {
            base_settings.collection_for(kind, language_id)
            for language_id in language_ids
            for kind in ("active", "reference", "excluded")
        }
    )
    public_collection_name_set = set(public_collection_names)
    uses_public_data_dir = any(
        _is_relative_to(Path(path).resolve(), public_data_dir)
        for path in dataset_paths
    )
    uses_public_collection_name = any(
        collection_name in public_collection_name_set
        for collection_name in collection_names
    )
    if uses_public_data_dir:
        raise RulePackageValidationError(
            "private package validation attempted to use public review-engine/data artifacts"
        )
    if uses_public_collection_name:
        raise RulePackageValidationError(
            "private package validation attempted to use public Chroma collection names"
        )

    return {
        "status": "passed",
        "private_artifact_root": str(private_settings.data_dir.parent),
        "private_data_dir": str(private_settings.data_dir),
        "private_chroma_path": str(private_settings.chroma_path),
        "private_collection_prefix": private_settings.collection_name,
        "dataset_paths": dataset_paths,
        "collections": collection_names,
        "public_data_dir": str(public_data_dir),
        "public_collection_names_checked": public_collection_names,
        "uses_public_data_dir": False,
        "uses_public_collection_name": False,
    }


def validate_rule_package_split_gate(
    package_root: Path,
    *,
    manifest_name: str = PACKAGE_MANIFEST_NAME,
    settings: Any | None = None,
    private_artifact_root: Path | None = None,
) -> dict[str, Any]:
    from review_engine.config import get_settings
    from review_engine.ingest.build_records import ingest_all_sources
    from review_engine.ingest.rule_loader import load_rule_runtime
    from review_engine.retrieve.search import GuidelineSearchService

    base_settings = settings or get_settings()
    package_payload = validate_rule_package(package_root, manifest_name=manifest_name)
    extension_root = Path(package_payload["extension_roots"][0]["resolved_path"]).resolve()
    language_id = str(package_payload["extension_roots"][0]["language_id"])
    package_id = str(package_payload["package_id"])
    package_version = str(package_payload["package_version"])
    artifact_root = _package_artifact_root(
        package_id=package_id,
        package_version=package_version,
        private_artifact_root=private_artifact_root,
    )
    private_settings = replace(
        base_settings,
        data_dir=artifact_root / "data",
        active_dataset_path=None,
        reference_dataset_path=None,
        excluded_dataset_path=None,
        chroma_path=artifact_root / "chroma",
        collection_name=_private_collection_prefix(package_id, package_version),
        active_collection_name=None,
        reference_collection_name=None,
        excluded_collection_name=None,
        extension_rule_roots=(extension_root,),
        default_language_id=language_id,
        strict_extension_loading=True,
    )

    try:
        private_runtime = load_rule_runtime(private_settings, language_id=language_id)
    except Exception as exc:
        raise RulePackageValidationError(
            f"private runtime strict load failed: {exc}"
        ) from exc

    extension_records = _records_from_root(
        [
            *private_runtime.active_records,
            *private_runtime.reference_records,
            *private_runtime.excluded_records,
        ],
        extension_root,
    )
    active_extension_records = _records_from_root(private_runtime.active_records, extension_root)
    if not extension_records:
        raise RulePackageValidationError(
            "private runtime strict load did not expose package extension records"
        )
    if not active_extension_records:
        raise RulePackageValidationError(
            "private runtime retrieval requires at least one active package extension record"
        )

    retrieval_rule_no = sorted(record.rule_no for record in active_extension_records)[0]
    try:
        ingest_summary = ingest_all_sources(private_settings)
        retrieved = GuidelineSearchService(private_settings).inspect_rule(
            retrieval_rule_no,
            language_id=language_id,
        )
    except Exception as exc:
        raise RulePackageValidationError(
            f"private runtime retrieval failed: {exc}"
        ) from exc
    if retrieved is None:
        raise RulePackageValidationError(
            f"private runtime retrieval did not return package rule: {retrieval_rule_no}"
        )
    if not _is_relative_to(Path(retrieved.source).resolve(), extension_root):
        raise RulePackageValidationError(
            f"private runtime retrieval returned non-package rule source: {retrieved.source}"
        )

    public_settings = replace(
        base_settings,
        extension_rule_roots=(),
        strict_extension_loading=True,
    )
    try:
        public_runtime = load_rule_runtime(public_settings, language_id=language_id)
    except Exception as exc:
        raise RulePackageValidationError(
            f"public-only runtime regression failed: {exc}"
        ) from exc

    private_rule_nos = {record.rule_no for record in extension_records}
    public_rule_nos = {
        record.rule_no
        for record in [
            *public_runtime.active_records,
            *public_runtime.reference_records,
            *public_runtime.excluded_records,
        ]
    }
    leaked_rule_nos = sorted(private_rule_nos & public_rule_nos)
    if leaked_rule_nos:
        raise RulePackageValidationError(
            "public-only runtime unexpectedly exposes package rules: "
            + ", ".join(leaked_rule_nos)
        )

    artifact_boundary = _validate_private_artifact_boundary(
        base_settings=base_settings,
        private_settings=private_settings,
        ingest_summary=ingest_summary.model_dump(),
    )

    return {
        "source_of_truth": "package_yaml",
        "validation_mode": "split_gate",
        "package": package_payload,
        "source_manifest_validation": {
            "status": "passed",
            "mode": "package_manifest_included_files",
            "source_manifest_files": package_payload["included"]["source_manifest_files"],
        },
        "private_runtime_strict_load": {
            "status": "passed",
            "language_id": private_runtime.language_id,
            "extension_rule_roots": private_runtime.extension_rule_roots,
            "extension_rule_nos": sorted(private_rule_nos),
        },
        "private_runtime_retrieval": {
            "status": "passed",
            "rule_no": retrieval_rule_no,
            "pack_id": retrieved.pack_id,
            "collection_prefix": private_settings.collection_name,
        },
        "public_only_runtime_regression": {
            "status": "passed",
            "language_id": public_runtime.language_id,
            "extension_rule_roots": public_runtime.extension_rule_roots,
            "private_rule_visible": False,
        },
        "artifact_boundary": artifact_boundary,
        "mutated_files": [],
    }


def _validate_extension_root(
    *,
    package_root: Path,
    relative_path: str,
) -> dict[str, Any]:
    extension_root = _resolve_package_relative_path(
        package_root=package_root,
        relative_path=relative_path,
        field_name="extension_roots",
        allow_root=True,
    )
    if not extension_root.exists() or not extension_root.is_dir():
        raise RulePackageValidationError(
            f"Extension root does not exist or is not a directory: {relative_path}"
        )

    manifest_path = extension_root / "manifest.yaml"
    root_manifest = _load_model(
        manifest_path,
        RuleRootManifest,
        label="runtime rule-root manifest",
    )
    runtime_files = {
        "pack_files": _validate_runtime_manifest_files(
            package_root=package_root,
            extension_root=extension_root,
            relative_paths=root_manifest.pack_files,
            field_name="pack_files",
            model_cls=RulePackManifest,
        ),
        "profile_files": _validate_runtime_manifest_files(
            package_root=package_root,
            extension_root=extension_root,
            relative_paths=root_manifest.profile_files,
            field_name="profile_files",
            model_cls=ProfileConfig,
        ),
        "policy_files": _validate_runtime_manifest_files(
            package_root=package_root,
            extension_root=extension_root,
            relative_paths=root_manifest.policy_files,
            field_name="policy_files",
            model_cls=PriorityPolicy,
        ),
    }
    return {
        "path": _package_relative_posix(package_root, extension_root),
        "resolved_path": str(extension_root),
        "manifest_path": str(manifest_path),
        "language_id": root_manifest.language_id,
        **runtime_files,
    }


def _validate_runtime_manifest_files(
    *,
    package_root: Path,
    extension_root: Path,
    relative_paths: list[str],
    field_name: str,
    model_cls: type[_ModelT],
) -> list[str]:
    normalized: list[str] = []
    for relative_path in relative_paths:
        resolved_path = _resolve_relative_path(
            base_root=extension_root,
            boundary_root=package_root,
            relative_path=relative_path,
            field_name=f"runtime manifest {field_name}",
            allow_root=False,
        )
        if not resolved_path.exists() or not resolved_path.is_file():
            raise RulePackageValidationError(
                f"Runtime manifest file does not exist: {relative_path}"
            )
        _load_model(resolved_path, model_cls, label=field_name)
        normalized.append(_package_relative_posix(package_root, resolved_path))
    return normalized


def _validate_included_files(
    *,
    package_root: Path,
    manifest: RulePackageManifest,
    extension_roots: list[dict[str, Any]],
) -> dict[str, list[str]]:
    included_payload = manifest.included
    included_by_field = {
        "pack_files": _validate_included_file_list(
            package_root=package_root,
            relative_paths=included_payload.pack_files,
            field_name="included.pack_files",
            model_cls=RulePackManifest,
        ),
        "profile_files": _validate_included_file_list(
            package_root=package_root,
            relative_paths=included_payload.profile_files,
            field_name="included.profile_files",
            model_cls=ProfileConfig,
        ),
        "policy_files": _validate_included_file_list(
            package_root=package_root,
            relative_paths=included_payload.policy_files,
            field_name="included.policy_files",
            model_cls=PriorityPolicy,
        ),
        "source_manifest_files": _validate_included_file_list(
            package_root=package_root,
            relative_paths=included_payload.source_manifest_files,
            field_name="included.source_manifest_files",
            model_cls=RuleSourceManifest,
        ),
    }

    for field_name in ("pack_files", "profile_files", "policy_files"):
        runtime_paths = {
            path
            for extension_root in extension_roots
            for path in extension_root[field_name]
        }
        included_paths = set(included_by_field[field_name])
        if runtime_paths != included_paths:
            missing = sorted(runtime_paths - included_paths)
            extra = sorted(included_paths - runtime_paths)
            details = []
            if missing:
                details.append(f"missing from package metadata: {', '.join(missing)}")
            if extra:
                details.append(f"not referenced by runtime manifest: {', '.join(extra)}")
            raise RulePackageValidationError(
                f"included.{field_name} must match runtime manifest {field_name}: "
                + "; ".join(details)
            )
    return included_by_field


def _validate_included_file_list(
    *,
    package_root: Path,
    relative_paths: list[str],
    field_name: str,
    model_cls: type[_ModelT],
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for relative_path in relative_paths:
        resolved_path = _resolve_package_relative_path(
            package_root=package_root,
            relative_path=relative_path,
            field_name=field_name,
            allow_root=False,
        )
        if not resolved_path.exists() or not resolved_path.is_file():
            raise RulePackageValidationError(
                f"Included package file does not exist: {relative_path}"
            )
        _load_model(resolved_path, model_cls, label=field_name)
        normalized_path = _package_relative_posix(package_root, resolved_path)
        if normalized_path in seen:
            raise RulePackageValidationError(
                f"Duplicate package file in {field_name}: {normalized_path}"
            )
        seen.add(normalized_path)
        normalized.append(normalized_path)
    return normalized


def _validate_provenance(
    *,
    package_root: Path,
    manifest: RulePackageManifest,
) -> dict[str, Any]:
    for checksum in manifest.provenance.checksums:
        resolved_path = _resolve_package_relative_path(
            package_root=package_root,
            relative_path=checksum.path,
            field_name="provenance.checksums.path",
            allow_root=False,
        )
        if not resolved_path.exists() or not resolved_path.is_file():
            raise RulePackageValidationError(
                f"Provenance checksum file does not exist: {checksum.path}"
            )
    return manifest.provenance.model_dump()


def _load_model(path: Path, model_cls: type[_ModelT], *, label: str) -> _ModelT:
    try:
        payload = _load_yaml(path)
    except FileNotFoundError as exc:
        raise RulePackageValidationError(f"Missing {label}: {path}") from exc
    try:
        return model_cls.model_validate(payload)
    except ValidationError as exc:
        raise RulePackageValidationError(f"Invalid {label} at {path}: {exc}") from exc


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RulePackageValidationError(f"YAML file must contain a mapping: {path}")
    return payload


def _resolve_package_relative_path(
    *,
    package_root: Path,
    relative_path: str,
    field_name: str,
    allow_root: bool,
) -> Path:
    return _resolve_relative_path(
        base_root=package_root,
        boundary_root=package_root,
        relative_path=relative_path,
        field_name=field_name,
        allow_root=allow_root,
    )


def _resolve_relative_path(
    *,
    base_root: Path,
    boundary_root: Path,
    relative_path: str,
    field_name: str,
    allow_root: bool,
) -> Path:
    raw_path = str(relative_path)
    if raw_path != raw_path.strip() or not raw_path.strip():
        raise RulePackageValidationError(f"{field_name} path must not be empty or padded")
    posix_path = PurePosixPath(raw_path)
    if posix_path.is_absolute():
        raise RulePackageValidationError(f"{field_name} path must be package-relative: {raw_path}")
    if not allow_root and raw_path in {".", "./"}:
        raise RulePackageValidationError(f"{field_name} path must reference a file: {raw_path}")
    if any(part == ".." for part in posix_path.parts):
        raise RulePackageValidationError(
            f"{field_name} path must not contain path traversal: {raw_path}"
        )

    resolved_path = (base_root / Path(*posix_path.parts)).resolve()
    if not _is_relative_to(resolved_path, boundary_root):
        raise RulePackageValidationError(
            f"{field_name} path escapes package root: {raw_path}"
        )
    return resolved_path


def _package_relative_posix(package_root: Path, path: Path) -> str:
    try:
        relative = path.resolve().relative_to(package_root)
    except ValueError as exc:
        raise RulePackageValidationError(f"Path escapes package root: {path}") from exc
    if not relative.parts:
        return "."
    return relative.as_posix()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
