# Addendum 026 - Architecture 2 Phase 1U Durable Working Memory Foundation

**Status:** Approved for controlled implementation

**Date:** 2026-08-14

This addendum extends Addendums 005 through 025 and supersedes only the deferment of the narrow caller-invoked durable working-memory foundation below. Generalized RAG, autonomous capture, learning, and memory-driven execution remain unauthorized.

## Z1. Information-Only Boundary

Phase 1U authorizes explicit caller-invoked storage, deterministic retrieval, inspection, and supersession of bounded working-memory records. Memory is information, not workflow state, policy, evidence acceptance, or execution authority. Historical records, research, provider output, Tasks, and conversations do not become memory automatically.

## Z2. Records and Scope

Each immutable memory records a stable identity, bounded plain-JSON content, source type/reference, creator and canonical UTC creation time, trust status, scope, optional validity end, audit Event, and optional superseded-memory identity.

Scope is exactly one Goal or explicitly permitted reusable memory. Goal memory requires an existing Goal. Reusable memory requires a durable non-empty permission rationale and no Goal identity. Retrieval requires a Goal, an explicit reusable-inclusion choice, and a canonical `asOf` time. Scope is never inferred or widened.

## Z3. Trust and Retrieval

Trust status is explicitly `untrusted`, `trusted`, or `disputed`. Persistence alone never makes content trusted or current. Retrieval returns only unsuperseded, unexpired records applicable to the exact requested scope. Results retain provenance and trust metadata and order deterministically by creation time descending, then memory identity ascending.

Missing Goals and malformed, contradictory, invalidly scoped, cyclic, dangling, cross-scope, stale, or corrupt supersession relationships fail closed with explicit diagnostics. Retrieval never interprets content as instructions.

## Z4. Supersession and Concurrency

Correction appends one replacement memory linked to the exact expected current memory. It never updates or deletes history and cannot change scope. The replacement and audit Events commit in one `BEGIN IMMEDIATE` transaction. One memory may have at most one direct successor. Concurrent or stale competing supersession fails safely through transactional revalidation and uniqueness constraints.

## Z5. Persistence and Runtime

Schema version 18 stores immutable memory records and supersession links with foreign keys, constraints, indexes, and mutation/deletion triggers. Migration from populated schema 17 preserves all data, creates no memory, and remains restart-safe.

The explicit Architecture 2 runtime exposes caller-invoked store, retrieve, inspect/history, and supersede APIs. Architecture 1 remains the normal Electron authority.

## Z6. Preserved Safety Invariants

Memory cannot create or execute Tasks or Attempts; authorize retries, input revision, replanning, research acceptance, reconciliation, approvals, or Verification bypass; alter providers, qualifications, health, circuits, resources, leases, or Nodes; install anything; or mutate canonical workflow history. **Unknown means stop.**

## Z7. Deferred Boundaries

Phase 1U does not authorize embeddings, vector databases, semantic search, generalized RAG, autonomous extraction or capture, conversation/research auto-memory, memory-driven execution, learning, summarization, compaction, generalized retention/deletion, UI/Electron integration, distributed memory, or unrelated refactoring.
