# Addendum 016 — Architecture 2 Phase 1K Bounded Concurrent Scheduling

**Status:** Approved for controlled implementation

**Date:** 2026-08-14

This addendum extends Addendums 005 through 015 and authorizes only bounded concurrent scheduling within one authoritative Architecture 2 process.

## P1. Concurrency Boundary

The Architecture 2 Orchestrator may execute independent ready Tasks concurrently. `maxConcurrentTasks` must be a positive integer and defaults to `1`. The configured limit is fixed for an Orchestrator instance and must never be exceeded.

Only one `run()` invocation may own an Orchestrator at a time. Overlapping invocations on the same Orchestrator are rejected. Multi-process and multi-instance orchestration remain unauthorized.

## P2. Deterministic Admission and Dependencies

Ready Tasks are considered for admission in persisted `createdAt` ascending order, then Task ID lexical ascending order. Completion order may reflect actual runtime completion and is not required to be deterministic.

Only canonical `ready` Tasks may be admitted. Dependency evaluation remains authoritative and successors become eligible only after required predecessor state is durably recorded. Concurrent execution does not weaken success, completion, predicate-waiting, or required-dependency-failure semantics.

## P3. Resources and Deferral

Resource-aware admission must atomically persist the workflow scheduling decision, active lease, `ready -> scheduled` Task transition, and corresponding Events. Existing transactional capacity enforcement remains authoritative.

If a ready Task cannot currently acquire an eligible resource or sufficient capacity, it remains `ready`. No Attempt is created and no retry budget is consumed. The Orchestrator continues considering later ready Tasks in deterministic order, allowing unrelated eligible work to proceed. A resource-deferred Task may be reconsidered after active work settles or during a later run.

Existing capacity leases provide exclusivity when a Task leases a location's full capacity. Phase 1K introduces no separate distributed or advisory locking mechanism.

## P4. Supervision and Task Isolation

Concurrent Tasks are supervised independently. One Task's execution failure, verification failure, retry, or approval requirement must not terminate or bypass supervision of unrelated admitted work. Fail-fast aggregate promise behavior is prohibited.

Existing per-Task Attempt numbering, retry budgets, verification authority, approval pause/resume, Failure records, optimistic concurrency, audit history, and lease release behavior remain unchanged.

## P5. Durability and Recovery

Canonical persisted Tasks remain the queue. Runtime slot accounting is process-local control state and does not create another queue or durable Task abstraction. The existing schema can represent multiple scheduled and running Tasks; no migration is required solely for concurrency.

Conservative interrupted-work recovery remains authoritative for every persisted scheduled or running Task. Phase 1K does not replay, migrate, fail over, or infer success for interrupted work whose outcome cannot be proven.

## P6. Acceptance Requirements

Controlled implementation must verify concurrent overlap of independent Tasks; strict concurrency-limit enforcement; deterministic admission across permutations and restart; dependency-safe dispatch; resource conflict deferral and later-task scanning; atomic scheduling/lease rollback; failure isolation; per-Task retry and approval behavior; concurrent durable state and restart reconstruction; single-flight invocation ownership; all existing regressions; TypeScript validation; production build; real file-backed SQLite verification; Electron startup regression; diff hygiene; and engineering-log updates.

## P7. Deferred Boundaries

Phase 1K does not authorize user cancellation, cancellation propagation, forced interruption, process termination, preemption, checkpointing, execution migration, node-loss recovery, failover, alternate-node retry, distributed locking, distributed consensus, multiple orchestrator instances, remote workers, speculative execution, dynamic load balancing, dynamic concurrency optimization, priority displacement, predicate execution, scheduler-triggered workstation inspection/application, UI work, Electron authority cutover, or generalized policy-engine infrastructure.
