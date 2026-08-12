# Addendum 007 — Architecture 2 Phase 1B Workflow Kernel

**Status:** Approved for controlled implementation

**Date:** 2026-08-12

This addendum extends Addendums 005 and 006. It authorizes only the guarded Task state machine and minimal persistence-backed Orchestrator for one pre-authored immutable graph revision.

## G1. Canonical Phase 1B Lifecycle

Phase 1B uses the canonical Task states already defined by Addendum 005. Its executable path is:

```text
planned -> ready -> scheduled -> running -> verifying -> succeeded
                                     |           |
                                     v           v
                                   failed      failed
```

`planned -> blocked` represents a required upstream failure. Cancellation and supersession remain valid domain terminal states but no cancellation workflow is introduced in this phase. Approval, retry, and replanning states are not entered by the Phase 1B Orchestrator.

One centralized state-machine module owns transition legality and evidence guards. Persistence independently enforces optimistic versions and atomic state-plus-event commits.

Guards require:

- satisfied dependencies before `ready`;
- a matching running Attempt before `running`;
- a matching successful Attempt before `verifying`;
- a matching passing Verification before `succeeded`;
- a matching failed or indeterminate Attempt before `running -> failed`;
- a matching rejecting Verification before `verifying -> failed`;
- a terminal reason for failed, cancelled, or superseded transitions;
- an exact optimistic version match.

Terminal states cannot transition through the ordinary workflow API.

## G2. Dependency and Selection Rules

The Orchestrator operates on exactly one persisted immutable Task Graph Revision.

- A `success` dependency is satisfied only when its predecessor is `succeeded`.
- A `completion` dependency is satisfied when its predecessor is in a canonical terminal state.
- Predicate dependencies remain waiting because Phase 1B does not implement a predicate evaluator.
- A failed, cancelled, superseded, or transitively failure-blocked predecessor makes a required success-dependent Task `blocked` with reason `required_dependency_failed`.
- Graph structure is never mutated during execution.
- Runnable Tasks are selected one at a time in ascending persisted `created_at`, then Task ID order.
- The graph is terminal when every Task is terminal or explicitly blocked by a required dependency failure.

## G3. Execution and Verification

The Orchestrator depends only on a small capability-neutral execution contract containing Task identity, Attempt identity/number, objective, inputs, and required capability IDs. Execution returns either structured success output/evidence or structured failure information.

Phase 1B supplies exactly one deterministic in-process test provider. It performs no network, model, external process, provider selection, or hardware operation. Tests configure per-Task success, verification rejection, or execution failure and can inspect execution counts.

Execution success is not Task success. A separate deterministic verifier inspects the returned evidence and persists a passing or failing Verification. Only a passing Verification permits `verifying -> succeeded`.

## G4. Atomic Workflow Persistence

No schema migration is required. Schema version 1 already represents every Phase 1B state and record.

The persistence contract is extended with deterministic graph/history queries and composite transactions for:

- Task transition plus running Attempt creation;
- Attempt terminal outcome, optional Failure, Task transition, and events;
- Verification, optional Failure, Task terminal transition, and events;
- recovery Failure, Task transition, and events.

Each composite operation uses one explicit SQLite transaction, optimistic Task version checking, and one or more chained append-only events. Failure rolls back every participating write.

## G5. Restart and Interrupted Work

The Orchestrator reconstructs all position from persisted Tasks, dependencies, Attempts, Verifications, and Failures. It never relies on in-memory execution history.

- Succeeded and failed Tasks are never automatically re-executed.
- Planned work whose dependencies became satisfied before restart becomes ready after restart.
- Attempt history and numbering survive restart.
- A persisted `running` Task must have a persisted running Attempt. On restart, Phase 1B does not replay it. The Attempt becomes `indeterminate`, a non-retryable `external_outcome_indeterminate` Failure is recorded, and the Task becomes `failed`, atomically.
- A persisted `scheduled` Task whose execution cannot be proven becomes a diagnosed failed Task and is not executed.
- A corrupted `running` Task without its required running Attempt causes explicit recovery failure rather than invented history.

This is the conservative no-retry implementation of Addendum 005 E16. Provider-specific reconciliation and safe retry policy remain future work.

## G6. Scope Boundary

Phase 1B does not authorize real AI/provider calls, provider routing, parallel execution, retries, diagnosis/research, planning/replanning, dynamic graph mutation, approval workflows, scheduling, node/GPU routing, memory, cloud execution, UI redesign, Architecture 1 migration/deletion, or distributed orchestration.
