# Addendum 019 — Architecture 2 Phase 1N External Outcome Reconciliation

**Status:** Approved for controlled implementation

**Date:** 2026-08-14

This addendum extends Addendums 005 through 018 and supersedes only the Phase 1L and Phase 1M prohibition on executing `reconciliation_required`. It authorizes the bounded caller-invoked reconciliation behavior below. All other deferred recovery behavior remains unauthorized.

## S1. Reconciliation Boundary

Phase 1N may reconcile one exact prior Attempt whose latest authoritative Phase 1L diagnosis has outcome certainty `indeterminate_external_outcome` and disposition `reconciliation_required`. Reconciliation is explicitly caller-invoked. It performs no startup, scheduler, continuous, or background polling.

A versioned provider-neutral reconciliation provider receives bounded persisted identity and attribution for the exact Task, Attempt, Failure, diagnosis, provider offering, compute binding, and external operation where available. The provider supplies evidence only. Trusted Architecture 2 code validates and interprets that evidence and selects exactly one conclusion:

- `proven_completed`;
- `proven_not_completed`;
- `remains_indeterminate`.

A reconciliation-provider timeout, exception, malformed response, or contradictory response is a provider failure, not evidence about the external effect. It fails closed and cannot become execution retry authority.

## S2. Authoritative-State Gate

Trusted reconciliation must fail closed unless the Task, latest Attempt, latest Failure for that Attempt, and latest diagnosis all exist, agree by exact identity and attribution, and remain current. The diagnosis must use the current trusted diagnosis policy/version, select `reconciliation_required`, and retain `indeterminate_external_outcome`. The source Attempt must remain terminal `indeterminate`; no superseding Attempt, Failure diagnosis, recovery action, or Task lifecycle action may have occurred.

The request and evidence must identify the same external operation. Persisted idempotency or reconciliation metadata is used when available and must agree exactly. Missing operation identity, stale requests, wrong Task/Attempt/Failure/diagnosis attribution, malformed evidence, contradictory evidence, or unprovable correspondence fails closed.

Provider output never directly mutates Task state. Only trusted-core persistence operations may commit a reconciliation decision and any resulting lifecycle transition.

## S3. Proven Completed

When trusted reconciliation concludes `proven_completed`:

1. The reconciliation decision and bounded evidence are persisted immutably.
2. The original Attempt remains unchanged as indeterminate historical truth.
3. No replacement Attempt is created.
4. The original work resumes only through the normal Verification path using the reconciled result and evidence.
5. Only a passing Verification may transition the Task to `succeeded`.
6. A rejecting Verification creates the normal immutable Verification Failure and trusted diagnosis.

Proof that an external effect happened is not proof that the Task acceptance criteria passed.

## S4. Proven Not Completed

When trusted reconciliation concludes `proven_not_completed`:

1. The reconciliation decision and bounded evidence are persisted immutably.
2. The original Attempt remains unchanged as unsuccessful indeterminate history.
3. Trusted core may authorize only the next immutable Attempt number and return the Task to governed eligibility.
4. The authorization is single-use and is consumed atomically by that exact fresh Attempt.
5. Existing total Attempt limits and current approval requirements remain authoritative.
6. The fresh Attempt uses normal provider resolution, resource scheduling, leases, execution, Verification, and failure diagnosis.
7. Reconciliation cannot broaden privacy, destination, permissions, side effects, cost, schemas, or approval scope and cannot bypass Phase 1M or create a parallel retry system.

If budget or approval gates prevent a fresh Attempt, the conclusion remains durable but creates no execution authority.

## S5. Remains Indeterminate

When trusted reconciliation concludes `remains_indeterminate`, the immutable decision and evidence are persisted and the Task remains stopped. No Attempt, Verification, `ready` transition, alternative offering, alternative Node, replay, reroute, migration, inferred success, or ordinary execution retry is permitted.

A later caller-invoked reconciliation may supply new evidence only as additional immutable history under the same canonical source authority. It must not create competing final authority. A later conclusive decision is permitted only when it supersedes an earlier inconclusive observation through explicit trusted ordering and uniqueness; conclusive decisions cannot be replaced or contradicted.

## S6. Identity, Idempotency, and Conflict

Reconciliation requests use deterministic source attribution and caller-provided provider identity/version. Repeating an identical request and evidence returns the existing immutable decision or observation. Conflicting conclusive authority for the same source Attempt, Failure, and diagnosis is rejected. Once a conclusive decision exists, later conflicting or inconclusive evidence cannot replace it.

Evidence is bounded, sanitized, and provider-neutral. Credentials, secrets, endpoint details, raw command lines, unrelated private content, and unbounded provider payloads are prohibited.

## S7. Durability and Atomicity

Schema version 11 adds immutable reconciliation decisions/evidence and single-use Attempt or Verification consumption relationships with stable foreign keys to the source Task, Attempt, Failure, and diagnosis. Migration from populated schema version 10 must preserve all existing history without fabricating reconciliation evidence.

When reconciliation causes a lifecycle transition, the reconciliation decision, evidence, Task update, consumption relationship where applicable, and Events commit atomically. A fresh Attempt consumes its authorization in the existing atomic Attempt-start transaction. Failure of any participating write rolls back the complete operation.

Close/reopen reconstruction preserves exact source attribution, provider identity/version, operation identity, evidence, conclusion, reason, timestamps, lifecycle result, consumption, and Event relationships. Direct update or deletion of reconciliation history is rejected. Malformed persisted relationships produce explicit corruption diagnostics.

## S8. Runtime and Existing Invariants

The explicit Architecture 2 runtime composition boundary exposes reconciliation using caller-supplied provider-neutral capability. Ollama and other specific external services are not trusted-core dependencies.

Phase 1K Task isolation, Phase 1L diagnosis authority, Phase 1M alternative gates, total Attempt limits, approval requirements, provider qualification/health, resource eligibility, leases, optimistic concurrency, immutable history, and Verification authority remain unchanged. Reconciliation of one Task cannot mutate or authorize another Task.

The core invariant is: **Unknown means stop.** An external operation that remains indeterminate must not be replayed, rerouted, retried, migrated, or treated as successful.

## S9. Acceptance Requirements

Controlled implementation must verify exact latest-authority admission; stale and superseded rejection; provider-neutral operation matching; malformed and contradictory evidence rejection; provider failure fail-closed behavior; immutable and idempotent decisions; conflict rejection; proven-completed Verification without a replacement Attempt; Verification-only Task success; proven-not-completed single-use next-Attempt authorization with Attempt, approval, provider, resource, and lease gates; indeterminate stop behavior; non-indeterminate Failure rejection; unrelated-Task isolation; schema-10 migration; SQLite close/reopen reconstruction; all Phase 1L and Phase 1M regressions; TypeScript validation; full automated tests; production build; runtime/import smoke tests; Electron startup regression; diff hygiene; living-document correction; and engineering-log updates.

## S10. Deferred Boundaries

Phase 1N does not authorize background reconciliation polling, continuous provider polling, scheduler-triggered reconciliation, arbitrary external discovery, circuit breakers, input-revision execution, planning or replanning, Task Graph mutation, governed research, web/model research, automatic installation, checkpointing, live migration, automatic background failover, cancellation/preemption, distributed workers, multiple Orchestrators, generalized policy-engine redesign, generalized tool execution, memory, UI work, Electron Architecture 2 authority cutover, or unrelated refactoring.
