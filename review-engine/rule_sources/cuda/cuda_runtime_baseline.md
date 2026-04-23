---
rule_source_id: cuda.cuda_runtime_baseline
language_id: cuda
dialect_id: null
profile_hints: [default]
pack_targets: [cuda_core, cuda_performance]
source_type: public_guideline_summary
source_ref:
  title: NVIDIA CUDA Runtime and Best Practices
  url: https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [cuda, gpu, kernel, runtime, performance]
status: drafted
---

# CUDA Runtime Baseline

## Scope

- This bundle covers CUDA C++ code that owns device memory, launches kernels, and coordinates streams or synchronization.
- It is optimized for reviewable local signals from `.cu` and `.cuh` patches rather than whole-program performance tuning.

## Candidate Canonical Rule Groups

- Error and lifecycle boundaries: kernel launch status, runtime API return handling, and explicit ownership for device or managed allocations.
- Synchronization and stream contracts: default-stream sequencing, device-wide synchronization, and transfer or launch overlap assumptions.
- Kernel safety boundaries: divergent barriers, host-device annotation drift, and launch or shared-memory contracts that should stay close to the kernel.
- Hot-path performance traps: atomic contention, warp divergence, and dynamic shared-memory sizing choices that are visible in the patch.

## Reference-Only Guidance

- Occupancy tuning, bank conflicts, and launch-configuration tradeoffs remain advisory unless the diff shows a concrete local contract break.
- Host-device residency strategy, prefetch policy, and transfer batching often need broader workload context and stay hybrid or reference guidance first.
