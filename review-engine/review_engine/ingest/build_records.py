from __future__ import annotations

from review_engine.config import Settings, write_json_file
from review_engine.ingest.chroma_store import ChromaGuidelineStore
from review_engine.ingest.rule_loader import discover_rule_languages, load_rule_runtime
from review_engine.models import IngestionSummary


def ingest_all_sources(settings: Settings, force_refresh: bool = False) -> IngestionSummary:
    del force_refresh
    languages = discover_rule_languages(settings) or [settings.default_language_id]
    store = ChromaGuidelineStore(settings)

    total_parsed = 0
    total_active = 0
    total_reference = 0
    total_excluded = 0
    total_organization_policy = 0
    total_cpp_core = 0
    aggregate_collections: dict[str, int] = {}
    aggregate_pack_counts: dict[str, int] = {}
    language_summaries: dict[str, dict[str, int | str]] = {}
    dataset_paths: dict[str, dict[str, str]] = {}
    default_runtime = None

    for language_id in languages:
        runtime = load_rule_runtime(
            settings,
            language_id=language_id,
            include_all_packs=True,
        )
        if default_runtime is None and language_id == settings.default_language_id:
            default_runtime = runtime

        active_path = settings.dataset_path("active", language_id)
        reference_path = settings.dataset_path("reference", language_id)
        excluded_path = settings.dataset_path("excluded", language_id)
        write_json_file(active_path, [record.model_dump() for record in runtime.active_records])
        write_json_file(reference_path, [record.model_dump() for record in runtime.reference_records])
        write_json_file(excluded_path, [record.model_dump() for record in runtime.excluded_records])

        store.rebuild_language(
            language_id=language_id,
            active_records=runtime.active_records,
            reference_records=runtime.reference_records,
            excluded_records=runtime.excluded_records,
        )

        parsed_total = sum(runtime.parsed_pack_counts.values())
        total_parsed += parsed_total
        total_active += len(runtime.active_records)
        total_reference += len(runtime.reference_records)
        total_excluded += len(runtime.excluded_records)
        all_language_records = [
            *runtime.active_records,
            *runtime.reference_records,
            *runtime.excluded_records,
        ]
        total_organization_policy += sum(
            1 for record in all_language_records if record.source_kind == "organization_policy"
        )
        total_cpp_core += sum(1 for record in all_language_records if record.pack_id == "cpp_core")
        aggregate_pack_counts.update(runtime.parsed_pack_counts)
        aggregate_collections.update(
            {
                settings.collection_for("active", language_id): len(runtime.active_records),
                settings.collection_for("reference", language_id): len(runtime.reference_records),
                settings.collection_for("excluded", language_id): len(runtime.excluded_records),
            }
        )
        language_summaries[language_id] = {
            "parsed": parsed_total,
            "active": len(runtime.active_records),
            "reference": len(runtime.reference_records),
            "excluded": len(runtime.excluded_records),
        }
        dataset_paths[language_id] = {
            "active": str(active_path),
            "reference": str(reference_path),
            "excluded": str(excluded_path),
        }

    default_runtime = default_runtime or load_rule_runtime(
        settings,
        language_id=settings.default_language_id,
        include_all_packs=True,
    )
    return IngestionSummary(
        total_parsed=total_parsed,
        organization_policy_records=total_organization_policy,
        cpp_core_records=total_cpp_core,
        active_records=total_active,
        reference_records=total_reference,
        excluded_records=total_excluded,
        active_dataset_path=str(settings.dataset_path("active")),
        reference_dataset_path=str(settings.dataset_path("reference")),
        excluded_dataset_path=str(settings.dataset_path("excluded")),
        collections=aggregate_collections,
        parsed_pack_counts=aggregate_pack_counts,
        public_rule_root=default_runtime.public_rule_root,
        extension_rule_roots=default_runtime.extension_rule_roots,
        languages=language_summaries,
        dataset_paths=dataset_paths,
    )
