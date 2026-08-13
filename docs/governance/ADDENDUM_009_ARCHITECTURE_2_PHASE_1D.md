# Addendum 009 — Architecture 2 Phase 1D Durable Work Queue

**Status:** Approved for controlled implementation

**Date:** 2026-08-13

This addendum extends Addendums 005 through 008 and authorizes only the durable work queue, complete graph admission, dependency resolution, deterministic scheduling, and queue inspection described below.

## I1. Canonical Durable Queue

The canonical Architecture 2 `Task` is the durable schedulable work unit. Persisted Tasks and their canonical lifecycle states constitute the Phase 1D queue. Phase 1D introduces no separate queue item, second Task abstraction, standalone queue table, in-memory authoritative queue, or external message broker.

SQLite remains the authoritative store. Queue state, dependency edges, Attempts, Failures, approvals, and audit events must survive process and machine restart. Architecture 1 task and JSON-state implementations remain unchanged and disconnected.

## I2. Complete Graph Admission

A Task Graph Revision intended for execution must be admitted with all of its Tasks and dependency edges in one transaction. The complete proposed graph is validated before records are written. Admission succeeds completely or leaves no revision, Task, dependency, or admission event visible.

Admission rejects unknown dependency endpoints, cross-revision edges, self-dependencies, duplicate dependency pairs, conflicting duplicate definitions, malformed predicate definitions, and cyclic graphs. Existing SQLite constraints remain defense in depth. Admitted graph structure remains immutable.

## I3. Acyclic Dependency Validation

Executable Task graphs must be acyclic. Validation uses deterministic Kahn topological processing:

1. Task IDs are sorted lexically.
2. Outgoing adjacency lists are sorted lexically.
3. Zero-indegree Tasks are processed in lexical Task-ID order.
4. A graph is valid only when every Task is processed.
5. Rejection reports remaining unresolved Task IDs in lexical order.

Unresolved Task IDs are not represented as exact cycle members. They may include Tasks downstream of a cycle. Exact strongly connected component identification is outside Phase 1D.

## I4. Dependency Resolution

- A `success` dependency is satisfied only when its predecessor is `succeeded`.
- A terminal unsuccessful predecessor blocks a required success-dependent Task using the existing `required_dependency_failed` semantics.
- A `completion` dependency is satisfied by any canonical terminal predecessor state.
- A `predicate` dependency remains durably waiting and inspectable with an explicit machine-readable reason. Predicate execution is not authorized.
- A missing predecessor in supposedly valid persisted state is corruption, not ordinary queue blocking, and fails closed.

## I5. Deterministic Scheduling

Only canonical `ready` Tasks are scheduler-eligible. Selection explicitly sorts eligible Tasks by:

1. persisted `createdAt` ascending;
2. Task ID lexical ascending.

Priority does not alter ordering in Phase 1D. Selection must not depend on database, filesystem, object, Map, Set, or input collection iteration order. Execution remains sequential.

## I6. Queue Inspection

Phase 1D provides a read-only deterministic projection of authoritative persisted state. It exposes Task state, dependencies and predecessor states, scheduler eligibility, stable blocking Task IDs and reasons, terminal reason, Attempt count, and latest relevant Failure information. Inspection creates no presentation-specific persisted state and requires no UI.

Malformed or structurally inconsistent persisted queue data must produce an explicit diagnostic. It must not be silently omitted, normalized, replaced with defaults, or treated as an empty queue.

## I7. Restart and Delivery Semantics

Phase 1B and Phase 1C recovery behavior remains authoritative. Previously scheduled or running work whose outcome cannot be proven is not automatically replayed. Running Attempts with uncertain outcomes become `indeterminate`, record `external_outcome_indeterminate`, and fail closed atomically. Retry and approval decisions continue to derive from durable records.

Architecture 2 expects at-least-once internal delivery and idempotent effect boundaries. Phase 1D makes no exactly-once execution claim and introduces no provider reconciliation mechanism.

## I8. Runtime and Scope Boundary

One authoritative G.R.A.C.I. runtime remains the initial assumption. Phase 1D does not authorize distributed consensus, multiple orchestrator leadership, concurrent/resource scheduling, provider or model routing, node/GPU selection, remote workers, dynamic planning or graph mutation, predicate execution, Architecture 1 migration, Electron runtime integration, UI work, cloud infrastructure, or an external broker.
