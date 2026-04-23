---
rule_source_id: cuda.cuda_tensor_core_deepening
language_id: cuda
dialect_id: null
profile_hints: [cuda_tensor_core]
pack_targets: [cuda_tensor_core]
source_type: public_guideline_summary
source_ref:
  title: CUDA WMMA and Tensor Core Programming
  url: https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [cuda, tensor-core, wmma, mma, ldmatrix]
status: drafted
---

# CUDA Tensor Core Deepening

## Scope

- This bundle deepens CUDA review for kernels that use WMMA fragments, Tensor Core instructions, or other warp-level matrix-math fast paths.
- It focuses on warp-collective execution, staging-layout contracts, and mixed-precision boundaries that are often visible from local kernel code.

## Candidate Canonical Rule Groups

- Warp-uniform Tensor Core participation for `wmma::load_matrix_sync`, `wmma::mma_sync`, `wmma::store_matrix_sync`, and inline matrix instructions.
- Inline Tensor Core PTX paths where tile shape, shared-memory staging, and operand alignment contracts must stay obvious.
- Mixed-precision accumulation and epilogue narrowing boundaries where low-precision inputs or outputs can hide a numerical contract.

## Reference-Only Guidance

- Architecture gating, fallback kernels, and feature support should stay visible enough that reviewers can tell whether the Tensor Core fast path is optional or required.
- WMMA fragment layout stays intentionally opaque, so wider interfaces should exchange memory-backed tiles rather than fragment internals.
