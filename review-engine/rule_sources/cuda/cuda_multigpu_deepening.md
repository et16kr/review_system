---
rule_source_id: cuda.cuda_multigpu_deepening
language_id: cuda
dialect_id: null
profile_hints: [cuda_multigpu]
pack_targets: [cuda_multigpu]
source_type: public_guideline_summary
source_ref:
  title: CUDA Multi-GPU Systems and NCCL
  url: https://docs.nvidia.com/cuda/cuda-programming-guide/03-advanced/multi-gpu-systems.html
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [cuda, multigpu, nccl, peer-access]
status: drafted
---

# CUDA Multi-GPU Deepening

## Scope

- This bundle deepens CUDA review for code that switches active devices, enables peer access, or launches NCCL collectives.
- It focuses on device-scoping and collective-ordering contracts that still matter at local diff granularity.

## Candidate Canonical Rule Groups

- Current-device ownership and repeated cudaSetDevice boundaries in orchestration code.
- Peer access and peer-copy topology assumptions together with capability and fallback visibility.
- NCCL communicator, group, and stream ordering boundaries that should remain legible from local code.

## Reference-Only Guidance

- Rank-to-device mapping and communicator lifetime often span more modules than a local diff, but should still stay reconstructable.
- Multi-device managed memory placement and cross-GPU data movement costs often depend on topology assumptions that remain hybrid guidance first.
