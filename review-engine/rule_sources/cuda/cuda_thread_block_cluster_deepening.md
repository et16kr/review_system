---
rule_source_id: cuda.cuda_thread_block_cluster_deepening
language_id: cuda
dialect_id: null
profile_hints: [cuda_thread_block_cluster]
pack_targets: [cuda_thread_block_cluster]
source_type: public_guideline_summary
source_ref:
  title: CUDA Thread Block Clusters and Distributed Shared Memory
  url: https://docs.nvidia.com/cuda/cuda-programming-guide/02-basics/intro-to-cuda-cpp.html
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [cuda, cluster, distributed-shared-memory, cooperative-groups]
status: drafted
---

# CUDA Thread Block Cluster Deepening

## Scope

- This bundle deepens CUDA review for kernels that use thread block clusters, `cluster_group`, `cluster.sync()`, or distributed shared memory.
- It focuses on launch-contract visibility, cluster-wide collective safety, and remote shared-memory ownership that should remain readable from local code.

## Candidate Canonical Rule Groups

- Cluster-aware kernel code should keep the launch contract visible between the kernel body and the launch site when correctness depends on cluster dimensions.
- Cluster-wide synchronization should remain a full-participant collective instead of being hidden under block-rank or lane-dependent control flow.
- Distributed shared-memory access should keep remote rank ownership and readiness boundaries explicit before remote shared data is read, written, or updated atomically.

## Reference-Only Guidance

- Cluster topology, grid-multiple requirements, and resource assumptions should stay reconstructable enough that reviewers can tell why the chosen cluster size is valid.
- Distributed shared-memory helpers should preserve remote rank, lifetime, and reuse boundaries instead of hiding them behind opaque abstractions.
