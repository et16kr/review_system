---
rule_source_id: cuda.cuda_wgmma_deepening
language_id: cuda
dialect_id: null
profile_hints: [cuda_wgmma]
pack_targets: [cuda_wgmma]
source_type: public_guideline_summary
source_ref:
  title: PTX ISA Asynchronous Warpgroup MMA
  url: https://docs.nvidia.com/cuda/parallel-thread-execution/index.html
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [cuda, wgmma, warpgroup, mma_async, wait_group]
status: drafted
---

# CUDA WGMMA Deepening

## Scope

- This bundle deepens CUDA review for Hopper-class warpgroup MMA code that uses `wgmma.mma_async`, `wgmma.commit_group`, `wgmma.wait_group`, or explicit warpgroup fences.
- It focuses on warpgroup-uniform participation, async-group completion ownership, and epilogue boundaries that should remain visible from local kernel code.

## Candidate Canonical Rule Groups

- Warpgroup MMA issue sites should stay warpgroup-uniform instead of hiding under lane-local or warp-local control flow.
- Commit-group, wait-group, and fence operations should keep async-group ownership explicit so reviewers can reconstruct who closes the outstanding MMA work.
- Epilogue or accumulator use should stay visibly behind the matching wait-group boundary before results are narrowed or published.

## Reference-Only Guidance

- Shared descriptor setup, staging shape, and fence placement should stay reconstructable enough that reviewers can tell why the warpgroup contract is valid.
- Matrix layout, fragment shape, and accumulator narrowing choices should remain visible enough that reviewers can follow the result contract without reverse-engineering helper layers.
