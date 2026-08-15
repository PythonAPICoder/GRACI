# Addendum 027 - Architecture 2 Phase 1V Governed Memory-Assisted Decision Support

**Status:** Approved for controlled implementation

**Date:** 2026-08-15

This addendum extends Addendums 005 through 026 and supersedes only the deferment of explicit caller-supplied working-memory citations on governed Task input revision and replanning. Autonomous memory retrieval, planning, replanning, and memory-driven execution remain unauthorized.

## A1. Explicit Citation-Only Boundary

Phase 1V authorizes an explicit caller-supplied set of durable working-memory records (`MemoryId`) to be cited, validated, and durably recorded as provenance on two governed decisions only: Task input revision and replanning. Memory is information and context only. No memory is ever retrieved automatically, inferred, or synthesized into a decision.

## A2. Eligibility, Scope, and Trust

Each citation must satisfy every Phase 1U record invariant and, at decision time, must be:

- present and not dangling (`Cited memory not found` otherwise);
- unsuperseded (`Cited memory is superseded` otherwise);
- unexpired relative to the decision timestamp (`Cited memory has expired` otherwise);
- `trusted` in trust status (`Cited memory must be trusted` otherwise);
- either scoped to the decision Goal exactly (`Cited memory is not scoped to the decision Goal`) or an explicitly permitted reusable record (`reusable` scope carrying durable permission).

Missing, expired, superseded, untrusted, disputed, or wrong-scope memory fails closed with an explicit diagnostic and does not block or weaken the underlying decision authority.

## A3. Deterministic Normalization

Citations are normalized before use: identifiers are validated, duplicates are rejected, ordering is canonicalized to `MemoryId` ascending, and the count is bounded by `MAX_MEMORY_CITATIONS_PER_DECISION = 16`. Duplicate citation in one decision is rejected (`Duplicate memory citation in one decision`).

## A4. Non-Authoritative Information Invariant

A memory citation never authorizes a decision, satisfies an authorization predicate, alters failure diagnosis/disposition, retryability, or outcome certainty, bypasses approval or Verification, changes circuit or Task state, or causes any Task/Attempt scheduling or state transition. Absence of a memory citation never blocks a valid decision. Disposition and authority remain driven solely by the Phase 1L diagnosis and (when present) Phase 1S research evidence.

## A5. Durable Immutable Provenance

Accepted citations are persisted as immutable links in a new `memory_decision_links` table, keyed by decision kind (`input_revision` or `replanning`), with foreign keys to the decision, memory record, Goal, and Task, a uniqueness constraint per decision, and CHECK constraints enforcing kind/column consistency. Links are mutation- and deletion-protected by triggers. Later supersession or expiry of a cited memory never alters completed historical provenance.

## A6. Transactional Atomicity and Coexistence

Decision, Task/revision state change, and citation provenance commit or roll back together in one `BEGIN IMMEDIATE` transaction. `researchEvidenceId` (Phase 1S) and `memoryIds` (Phase 1V) may both be present and are validated and inspectable independently; memory never substitutes for research and never changes the research-driven disposition requirement. Existing-branch replay is idempotent by comparing stored memory-link identity with the command set and does not revalidate eligibility of already-completed decisions.

## A7. Persistence and Runtime

Schema version 19 stores the citation links with foreign keys, constraints, indexes, and mutation/deletion triggers. Migration from populated schema 18 preserves all data, creates no citations, and remains restart-safe. The explicit Architecture 2 runtime exposes memory-citation inspection for input revision and replanning. Architecture 1 remains the normal Electron authority.

## A8. Preserved Safety Invariants

Phase 1V preserves every Phase 1U safety invariant. Out of scope: autonomous planning, replanning, or retrieval; vector/RAG/embeddings; scheduler or concurrency changes; UI; distributed workers; and a generalized policy engine. **Unknown means stop.**
