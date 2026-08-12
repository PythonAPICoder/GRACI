# Addendum 006 — Architecture 2 Phase 1A Decisions

**Status:** Approved for controlled implementation

**Date:** 2026-08-12

This addendum extends and, where stated, supersedes parts of Addendum 005. It records the Product Owner and Architect decisions authorizing only the Architecture 2 Phase 1A durable domain and persistence kernel.

## F1. Approved Persistence Decisions

1. SQLite is the initial primary persistence engine.
2. Architecture 2 uses relational current state plus meaningful append-only events. Full event sourcing is not authorized.
3. One authoritative G.R.A.C.I. runtime owns orchestration initially. Distributed consensus and high availability are out of scope. Optimistic concurrency fields shall expose accidental stale writes.
4. Task graph revisions and their structural records are historical and immutable. Replanning creates another revision.
5. Terminal execution Attempts are immutable. Each retry creates another Attempt.
6. Goal success derives from explicit criteria and verified required work, never percentage or heuristic aggregation.
7. Artifact content belongs in configurable local filesystem storage. SQLite stores identity, provenance, hash, and metadata, not large binary content.
8. Events are append-only and structured for tamper evidence. Phase 1A may use a deterministic SHA-256 hash chain; external signing and PKI are out of scope.
9. Cloud execution and routing are disabled by default. Phase 1A performs no cloud calls.
10. Initial approvals are single-user/local and scoped to a recorded action and relevant workflow entity. Standing/global approval UX is out of scope.

These decisions resolve Addendum 005 E21 items 1, 2, 3 for the initial runtime, 4 for initial artifact storage, 7, 8 for Phase 1A, and 12. Later changes require a new addendum.

## F2. Phase 1A Boundary

Phase 1A consists only of:

- strongly typed canonical identifiers and persistence-oriented representations for Goal, Goal success criterion, Task, Task dependency, Task Graph Revision, Attempt, Verification, Failure, Approval, Artifact metadata/provenance, and Event;
- a provider-independent persistence contract;
- a local SQLite provider using the built-in `node:sqlite` API when qualified against the actual Node, Electron, TypeScript, build, and test environments;
- schema migration version 1, constructible from an empty database;
- transactional state-plus-event writes, foreign keys, integrity constraints, deterministic queries, optimistic versions, and restart-safe storage;
- isolated, disposable persistence tests.

The Orchestrator, Planner, Executor, provider routing, retry and verification engines, approval UI, scheduler, node routing, memory retrieval, cloud routing, UI redesign, and deletion of Architecture 1 remain unauthorized.

## F3. Phase 1A Persistence Invariants

- Every public create or state-update operation commits its corresponding event in the same explicit transaction.
- Failure to write either state or event rolls back both.
- Events cannot be updated or deleted through the persistence contract; SQLite triggers also reject direct updates or deletes.
- Event sequence is database-assigned and queries are explicitly ordered.
- The event hash is deterministic over canonical event content and the previous event hash.
- Foreign keys are enabled on every connection.
- Migrations are ordered, transactional, recorded in `schema_migrations`, and reflected in SQLite `user_version`.
- Goal and Task state records carry optimistic versions. Updates must match the expected version and increment exactly once.
- Task graph revision identities, task structural fields, and dependency edges are not rewritten by state updates.
- Attempts use unique `(task_id, attempt_number)` identities and are never overwritten by retries.
- Terminal Attempts, all Attempt deletions, graph revision mutation/deletion, dependency mutation/deletion, and event mutation/deletion are rejected at the database boundary.
- Test and runtime database paths are supplied by callers. Reusable source code contains no machine-specific database or artifact path.

## F4. Compatibility

Architecture 1 remains in place. Phase 1A is an isolated `src/architecture2` kernel and does not change existing task management, Ollama integration, Electron UI, configuration, or persistent JSON state. A later approved phase must define migration/import and runtime composition before Architecture 2 becomes the live application authority.
