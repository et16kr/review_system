from __future__ import annotations

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

_ModelT = TypeVar("_ModelT", bound=StrictAuthoringModel)


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
