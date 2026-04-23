---
rule_source_id: cuda.cuda_tma_deepening
language_id: cuda
dialect_id: null
profile_hints: [cuda_tma]
pack_targets: [cuda_tma]
source_type: public_guideline_summary
source_ref:
  title: CUDA Tensor Memory Accelerator and Tensor Map Contracts
  url: https://docs.nvidia.com/cuda/archive/13.1.1/cuda-programming-guide/04-special-topics/async-copies.html
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [cuda, tma, cutensormap, cp_async_bulk_tensor, mbarrier]
status: drafted
---

# CUDA TMA Deepening

## Scope

- This bundle deepens CUDA review for Tensor Memory Accelerator code that uses `CUtensorMap`, bulk tensor async copies, tensor-map mutation helpers, or proxy-fence publication paths.
- It focuses on completion boundaries, tensor-map ownership, and descriptor publication contracts that should remain visible from the local kernel and launch path.

## Candidate Canonical Rule Groups

- Bulk tensor async copies should keep the barrier completion boundary visible before shared tiles are consumed.
- Tensor maps should keep their transport contract explicit, especially when code chooses between `__grid_constant__`, constant-memory, or global-memory pointer paths.
- On-device tensor-map mutation should show the proxy-fence or descriptor publication step before later TMA use reuses the updated map.

## Reference-Only Guidance

- Tensor shape, alignment, multicast topology, and coordinate construction should stay reconstructable enough that reviewers can tell why the tensor transfer contract is valid.
- Barrier byte counts, completion mechanism choice, and bulk async-group ownership should remain visible instead of disappearing behind opaque wrappers.
