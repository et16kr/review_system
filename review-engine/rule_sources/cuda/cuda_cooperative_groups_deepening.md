---
rule_source_id: cuda.cuda_cooperative_groups_deepening
language_id: cuda
dialect_id: null
profile_hints: [cuda_cooperative_groups]
pack_targets: [cuda_cooperative_groups]
source_type: public_guideline_summary
source_ref:
  title: CUDA Cooperative Groups
  url: https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/cooperative-groups.html
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [cuda, cooperative-groups, grid-sync, tiled-partition]
status: drafted
---

# CUDA Cooperative Groups Deepening

## Scope

- This bundle deepens CUDA review for kernels that create or synchronize cooperative groups beyond plain block-level `__syncthreads()`.
- It focuses on collective participation, grid-wide synchronization ownership, and subgroup shape contracts that remain visible at local diff granularity.

## Candidate Canonical Rule Groups

- Collective group creation and partitioning boundaries for `tiled_partition`, `labeled_partition`, and related subgroup APIs.
- Grid-wide synchronization and cooperative launch ownership for kernels that call `this_grid()` or `grid.sync()`.
- Group-level sync placement where subgroup rank or lane-dependent control flow can violate the collective contract.

## Reference-Only Guidance

- Specialized group shapes and tile ownership should stay explicit enough that reviewers can connect subgroup size back to algorithm intent.
- Cooperative launch residency limits and large-scale synchronization assumptions often span launch code, but should still remain reconstructable.
