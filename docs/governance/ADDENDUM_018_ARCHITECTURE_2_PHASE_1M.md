# Addendum 018 — Architecture 2 Phase 1M Bounded Alternative Recovery

**Status:** Approved for controlled implementation

**Date:** 2026-08-14

This addendum extends Addendums 005 through 017 and supersedes only the Phase 1L prohibition on executing the two dispositions named below. It authorizes bounded alternative recovery after a proven unsuccessful Attempt. All other Phase 1L dispositions remain non-executable.

## R1. Authorized Recovery Boundary

Phase 1M may execute exactly two authoritative latest Phase 1L dispositions:

- `alternative_offering_recommended`
- `alternative_node_recommended`

Recovery is caller-invoked trusted-core behavior. It creates at most one immutable recovery decision for the authoritative diagnosis and does not create a background failover loop. A rejected or unavailable alternative creates no Attempt. An authorized alternative returns through the normal Architecture 2 scheduling, Attempt, execution, Failure, diagnosis, lease, and Verification paths.

## R2. Authoritative-State Gate

Recovery must fail closed unless the Task, failed Attempt, latest relevant Failure, and latest diagnosis all exist, agree by identity and attribution, and remain current. The diagnosis must use the current Phase 1L policy/version and select the exact requested alternative disposition. Its outcome must be `proven_unsuccessful`; indeterminate, completed, malformed, stale, superseded, approval, reconciliation, and other dispositions cannot authorize alternative execution.

The total persisted Attempt count must remain below the Task's existing maximum. Recovery never resets or creates a second retry budget. Any current approval requirement remains authoritative. A replacement that materially broadens privacy destination, permissions, side-effect class, schemas, cost, or approval scope is ineligible; retry cannot bypass, infer, or expand approval.

## R3. Alternative Offering

Alternative-offering recovery reuses the existing deterministic provider resolver with the failed Attempt's offering explicitly excluded. The candidate must satisfy the Task's caller-supplied capability contract and all existing qualification, health, privacy, permission, format, feature, schema, side-effect, quality, latency, and cost constraints. The selected offering must differ from the failed offering and must bind to the execution adapter used for the new Attempt.

The resolver decision, recovery decision, and changed-condition evidence identify the excluded and selected offering. If no eligible different offering exists, the recovery decision records that result and no Task transition or Attempt occurs.

## R4. Alternative Node

Alternative-node recovery reuses the existing deterministic resource scheduler with the failed Node and failed offering location excluded as applicable. The selected location and Node must be enabled, active, healthy under current freshness policy, privacy compatible, capacity eligible, compatible with the retained offering, and genuinely different from the failed binding.

The resource selection is recorded in the recovery decision. Normal resource scheduling revalidates eligibility and atomically acquires a lease when the Task is admitted; a recovery decision is not a lease and cannot reserve or bypass capacity. If no eligible different binding exists, no Task transition or Attempt occurs.

## R5. Durability, Ordering, and Consumption

Every recovery request records one immutable decision and audit Event. An authorized decision atomically records relevant changed-condition evidence and returns the Task from its diagnosed failed state to `ready` through the controlled Phase 1M recovery operation. The evidence commit precedes creation of the new Attempt. The decision may authorize only the next immutable Attempt number and is consumed only by an Attempt carrying its selected offering and, for Node recovery, selected Node/location binding.

Recovery identity and source diagnosis are unique. Repetition returns the same decision; conflicting reuse is rejected. Close/reopen reconstruction preserves decision, candidate selection, prior and replacement bindings, disposition, evidence, Attempt relationship, and Event history. Malformed or contradictory persisted recovery state produces an explicit diagnostic.

## R6. Failure and Isolation

An alternative Attempt that fails records a normal immutable Failure and returns to Phase 1L diagnosis. A later alternative requires a new authoritative diagnosis, remaining total Attempt budget, and a new genuinely changed binding. This prevents uncontrolled loops while allowing bounded chains across distinct Attempts.

Phase 1K concurrency isolation remains authoritative. Recovery of one Task cannot mutate or authorize another Task. Existing lease capacity, release, dependency, optimistic-concurrency, verification, and audit guarantees remain unchanged.

## R7. Safety Invariants

- An indeterminate external outcome always remains `reconciliation_required` and never routes to another offering or Node.
- Failed offering, Node, or location exclusions are explicit resolver/scheduler inputs and deterministic rejection reasons.
- No valid alternative means no new Attempt.
- Changed-condition evidence and the recovery decision are durable before the new Attempt.
- Attempt limits, approval requirements, provider qualification/health, privacy, policy constraints, Node health/state, location eligibility, and lease capacity remain authoritative.
- Stale or superseded diagnosis and recovery state fails closed.
- Provider output remains evidence; only normal Verification may produce Task success.

## R8. Acceptance Requirements

Controlled implementation must verify different eligible offering and Node selection; exclusion of failed bindings; deterministic selection; no-candidate behavior; stale diagnosis rejection; indeterminate-outcome prohibition; approval and Attempt-limit enforcement; evidence-before-Attempt ordering; immutable next Attempt numbering; normal lease acquisition and release; normal Verification; failed-recovery rediagnosis; unrelated-Task isolation; schema migration and SQLite close/reopen reconstruction; all Phase 1L regressions; TypeScript validation; full tests; production build; relevant runtime/import smoke tests; Electron startup regression; diff hygiene; and engineering-log and living-document updates.

## R9. Deferred Boundaries

Phase 1M does not authorize reconciliation execution or APIs, input revision, replanning, Planner implementation, graph mutation, research execution, web/model research, automatic model/provider installation, circuit breakers, checkpointing, migration of Tasks or live execution, cancellation/preemption, distributed workers, multiple Orchestrators, generalized policy-engine redesign, UI work, or Electron Architecture 2 authority cutover.

Node recovery means a new Attempt after a proven unsuccessful prior Attempt. It does not mean resuming, moving, or replaying interrupted or indeterminate work.
