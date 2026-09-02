# ACC-0007: Phase 8E Stage 1 projection foundation

> Classification: durable Product Owner acceptance record
> State: PRODUCT OWNER ACCEPTED
> Accepted by: Product Owner
> Recorded: 2026-09-02

## Accepted scope

The Product Owner accepts the Phase 8E Stage 1 fixture-only projection foundation.
The accepted implementation consists of the separate `phase8e` package, its
synthetic repository and memory fixtures, and its focused deterministic tests. It
provides:

- an explicit typed repository catalog and exact local Git-commit reads;
- exact-ID governed-memory fixture reads with metadata-only content by default;
- deterministic Markdown rendering with active-content, link, path, and secret
  controls;
- complete source and output hashes, immutable generation directories, atomic
  current-generation selection, and source-race rejection; and
- manifest and tree verification that detects mutation and unmanifested output.

Focused warning-strict verification passed 24 Stage 1 tests. The combined memory,
Phase 4, Phase 8E, and governance verification passed 111 tests. A final Stage 1 and
governance rerun passed 30 tests. Documentation links, fixture parsing, compilation,
prose-style checks, and `git diff --check` also passed.

The complete repository suite was not repeated because the accepted resident owned
loopback port 8766. The running service was not changed or stopped. This limits the
record to the named focused evidence.

## Promotion and Stage 2 authorization

On 2026-09-02, the Product Owner approved all remaining Stage 1 steps. The accepted
implementation was committed as `023a5ff9c78b549ac9d5d80ac3a3f1b92048ca12`,
fast-forwarded to local `main`, and pushed to `origin/main`.

The Product Owner also authorized all Stage 2 work within the accepted Phase 8E
design. Stage 2 may inspect the local Windows security capabilities, record the
exact supported plan, and implement and verify the dedicated standard viewer
identity, same-volume sibling staging and projection roots, least-privilege NTFS
ACLs, source isolation, projection-path application control, bounded local launcher,
rollback, synthetic validation, and durable evidence. Exact host facts and selected
controls must be recorded before dependent mutation, and the implementation must not
weaken an existing security boundary.

## Authority boundary

This acceptance does not claim Stage 1 deployment, real-data validation, Obsidian
qualification, or human-interface acceptance. Stage 2 authorization does not permit
Obsidian installation or configuration, access to real governed memory, real-data
projection, network or firewall changes, automatic refresh, resident or ordinary
runtime integration, or Stage 3 and later work. Those actions remain separately
controlled by the accepted design.
