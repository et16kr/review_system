---
rule_source_id: dockerfile.dockerfile_runtime_baseline
language_id: dockerfile
dialect_id: dockerfile_v1
profile_hints: [default, production_runtime]
pack_targets: [dockerfile_best_practices, container_security]
source_type: public_guideline_summary
source_ref:
  title: Dockerfile Runtime Review Baseline
  url: https://docs.docker.com/build/building/best-practices/
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [dockerfile, images, security, reproducibility]
status: drafted
---

# Dockerfile Runtime Baseline

## Scope

- This bundle covers Dockerfile build reproducibility, runtime privilege, and supply-chain visibility.
- The focus is not aesthetic formatting but whether the built image is explainable, repeatable, and minimally privileged.

## High-Signal Review Areas

- Pin base images deliberately, and treat tag-only references as still mutable unless a digest locks the exact artifact; keep package index refresh coupled to install steps.
- Avoid root runtime defaults unless the workload explicitly requires them.
- Keep COPY scopes narrow enough to reduce cache churn and accidental secret inclusion.
- Keep build-time credentials out of `ARG`/`ENV` when BuildKit secret mounts or external secret injection can carry them without ending up in image history.
- Treat remote downloads, remote URL `ADD`, and shell-piped bootstrap inside image builds as high-trust exceptions.
- Review full distribution upgrades in images as a reproducibility decision, not just a convenience command.

## Candidate Canonical Rule Groups

- Base image reproducibility: mutable `latest`, version tags without digests, and upgrade drift.
- Runtime privilege: `USER root`, build-vs-runtime separation, and least-privilege final stages.
- Build context hygiene: `COPY . .`, `.dockerignore`, and secret or cache bleed-through.
- Build-time secret handling: credential-bearing `ARG`/`ENV`, secret mounts, and image-history exposure.
- Artifact bootstrap: remote URL `ADD`, `curl | sh`, provenance checks, and explicit version pinning.

## Reference-Only Guidance

- Multi-stage builds, ownership-fixing layers, and build cache strategy often belong in reference-only guidance unless the diff shows a concrete hazard.
- Review Dockerfiles through the question "what exact artifact do we build, from which pinned inputs, with which runtime privileges?"
