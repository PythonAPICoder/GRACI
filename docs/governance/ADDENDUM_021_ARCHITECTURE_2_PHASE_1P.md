# Addendum 021 - Architecture 2 Phase 1P Governed Task Input Revision

**Status:** Approved for controlled implementation

**Date:** 2026-08-14

This addendum extends Addendums 005 through 020 and supersedes only the prior deferment of input-revision execution. It authorizes the narrow caller-invoked Task-input revision behavior below. Every other Phase 1O deferral and all earlier deferrals not expressly changed here remain in force.

## U1. Narrow Authorization

Phase 1P may execute only the authoritative latest Phase 1L disposition `input_revision_required` for one exact failed canonical Task. The operation is caller-invoked trusted-core behavior. It does not authorize planning, replanning, Task Graph mutation, Goal revision, automatic repair, background processing, or a generalized data-editing API.

The revised value may replace only the canonical Task `inputs` object. Task objective, title, required capabilities, graph identity, dependencies, privacy class, priority, retry policy, verification plan, required status, and all other structural or policy fields remain unchanged.

## U2. Exact Authority Chain

Input revision must fail closed unless this complete durable authority chain exists and agrees exactly:

1. The Task exists and is currently `failed`.
2. The latest immutable Attempt for that Task exists and is terminal `failed`.
3. The latest Failure for that exact Attempt exists.
4. The current trusted Phase 1L diagnosis for that exact Failure exists under the current diagnosis policy identity/version.
5. The diagnosis identifies that Task, Attempt, and Failure exactly, has outcome certainty `proven_unsuccessful`, and selects `input_revision_required`.
6. The failed Attempt's immutable input snapshot exactly matches the Task's current canonical inputs.
7. No later Attempt, Failure authority, superseding Task state, alternative-recovery decision, or reconciliation decision has displaced or conflicted with that diagnosis.

Missing, stale, superseded, malformed, contradictory, or ineligible authority is not repairable by inference. It produces no revision and no execution authority.

## U3. Task-Input-Only Constraint

Revised inputs must be a finite, acyclic, plain JSON object. They may contain only JSON-compatible object, array, string, finite-number, Boolean, and null values. Class instances, non-finite numbers, functions, symbols, undefined values, cyclic values, and non-object roots are rejected.

Authorization computes deterministic canonical SHA-256 digests for both the prior and revised inputs. The revised digest must differ from the prior digest. Key reordering or another canonically equivalent representation is not a meaningful change and must be rejected.

The atomic Task update may change only:

- `inputs` to the exact authorized revised object;
- lifecycle state from `failed` to `ready`;
- `terminalReason` and `completedAt` to absent;
- optimistic version and update timestamp as required by the normal lifecycle write.

No other Task field may change.

## U4. Immutable History and Canonical Meaningful Change

The failed Attempt, its exact input snapshot, Failure, diagnosis, prior Task history, Events, Verifications, approvals, routing decisions, leases, circuit history, alternative recovery, and reconciliation history remain immutable. Input revision appends authority; it never edits or recasts prior execution history.

Each accepted revision records the exact Task, failed Attempt, Failure, diagnosis, prior inputs and digest, revised inputs and digest, actor, canonical UTC authorization time, exact next Attempt number, and audit Event. One diagnosis may authorize at most one immutable revision. Equivalent repetition returns the existing authority; conflicting identity or content reuse is rejected.

## U5. Durable Exact Single-Use Next Attempt

An accepted revision may authorize only `latest failed Attempt number + 1`. It does not reset or create another retry budget. The total existing Attempt limit must have remaining capacity before authorization, and any pending approval remains authoritative.

The revision is pending authority until consumed atomically by the exact next Attempt. Attempt start must prove all of the following inside its write transaction:

- the revision is still pending and belongs to the same Task;
- no competing alternative-recovery or reconciliation authority is pending;
- the Attempt number is exactly the revision's recorded next number;
- the Attempt is a fresh normal `running` Attempt for the exact Task;
- the complete immutable Attempt input snapshot contains the authorized revised inputs and the Task's unchanged objective and required capabilities;
- the Task's current inputs, lifecycle state, and optimistic version still match the revision authority;
- all normal provider resolution, circuit filtering and probe rules, resource scheduling, lease, approval, Attempt-limit, and concurrency controls pass.

The revision consumption and Attempt creation commit atomically. A consumed revision cannot authorize another Attempt. A pending revision cannot be skipped by starting an unbound Attempt.

## U6. Concurrency and Transaction Boundary

Every authorization gate, including latest Task/Attempt/Failure/diagnosis authority, prior-input correspondence, conflict checks, Attempt limit, pending approval, canonical meaningful change, expected Task version, exact allowed Task mutation, and Event correspondence, must be reconstructed and revalidated inside the same SQLite `BEGIN IMMEDIATE` transaction that writes the revision, Event, and Task update.

Pre-transaction reads may support diagnostics or request construction but are never sufficient authority. Concurrent approval, supersession, recovery, reconciliation, Attempt creation, or another revision must either serialize before authorization and be observed by its gates or cause the transaction to fail closed. Conditional writes, uniqueness constraints, foreign keys, immutable-history triggers, and optimistic concurrency remain defense in depth.

## U7. Normal Controls and Unknown Outcomes

Input revision changes data, not policy or execution authority. It cannot bypass or broaden privacy, destination, permissions, side-effect class, schemas, qualification, health, cost, approval scope, circuit state, probe binding, Node eligibility, location eligibility, lease capacity, retry limits, Verification, or Task isolation.

Provider output remains evidence only. The revised Attempt follows normal execution, Failure diagnosis, and Verification. Only a passing normal Verification may transition the Task to `succeeded`.

The Phase 1N invariant remains absolute: **Unknown means stop.** An indeterminate external outcome cannot select `input_revision_required`, authorize revised execution, be converted to proven non-completion, or be replayed, rerouted, retried, migrated, replaced, or treated as successful through Phase 1P.

## U8. Persistence and Reconstruction

Schema version 13 stores immutable input-revision authority and immutable single-use consumption relationships with stable foreign keys to the exact Task, failed Attempt, Failure, diagnosis, Event, and consuming Attempt. Migration from populated schema version 12 preserves all existing history and fabricates no input revision or consumption.

Close/reopen reconstruction must preserve exact attribution, prior and revised inputs and digests, actor, time, next Attempt number, Event, pending/consumed state, and consuming Attempt relationship. Direct update or deletion of revision or consumption history is rejected. Malformed persisted values or relationships produce explicit corruption diagnostics.

## U9. Acceptance Requirements

Controlled implementation must verify exact latest-authority admission; Task-input-only mutation; canonical meaningful-change enforcement; malformed and cyclic input rejection; stale, superseded, conflicting-recovery, indeterminate-outcome, Attempt-limit, and pending-approval rejection; all authorization gates reconstructed inside `BEGIN IMMEDIATE`; concurrent approval or supersession fail-closed behavior; immutable prior Attempt snapshots and history; idempotent equivalent repetition and conflicting reuse rejection; exact next-Attempt numbering and full input-snapshot binding; atomic single-use consumption; inability to skip pending authority; normal provider, circuit, probe, resource, lease, approval, concurrency, Failure, and Verification controls; unknown-outcome stop behavior; unrelated-Task isolation; schema-12 to schema-13 migration without fabricated revisions; SQLite close/reopen reconstruction; prior Phase 1L through Phase 1O regressions; TypeScript validation; complete tests; production build; runtime/import checks; Electron startup regression; diff hygiene; and engineering-log and living-document updates.

## U10. Explicit Non-Goals and Deferred Boundaries

Phase 1P does not authorize Goal input or acceptance-criteria revision, Task objective or structural revision, Task Graph mutation, dependency changes, planning/replanning, Planner implementation, automatic or model-authored input repair, background revision, generalized policy-engine redesign, standing approval changes, retry-budget reset, reconciliation inference, automatic alternative recovery, circuit automation, research, web/model research, capability discovery, automatic installation, cancellation/preemption, checkpointing, live migration, interrupted-work failover, distributed workers, multiple Orchestrators, generalized tool execution, memory, UI work, or Electron Architecture 2 authority cutover.

All Phase 1O deferred boundaries and all earlier deferrals remain preserved except the input-revision-execution deferment expressly superseded by this addendum.
