# Addendum 024 - Architecture 2 Phase 1S Research-Assisted Recovery

**Status:** Approved for controlled implementation

**Date:** 2026-08-14

This addendum extends Addendums 005 through 023 and supersedes only the Phase 1R prohibition on the narrow accepted-evidence use described below. Autonomous research, automatic recovery, and all other deferred behavior remain unauthorized.

## X1. Narrow Alternate Source Admission

The existing caller-invoked `authorizeInputRevision` and `authorizeReplanning` commands may optionally cite one exact Research Evidence identity. Without a citation, Phase 1P and Phase 1Q behavior is unchanged. With a citation, a current trusted `research_recommended` and `proven_unsuccessful` diagnosis may serve as the source disposition only for the same existing action command and its existing validations.

Accepted evidence supports the action but does not execute, authorize, plan, revise, retry, or mutate anything by itself. Merely recorded, rejected, stale, unrelated, malformed, mismatched, or superseded evidence fails closed.

## X2. Exact Authority and Transaction

Inside the existing SQLite `BEGIN IMMEDIATE` action transaction, persistence must prove the exact Research Request, Evidence, accepted final Decision, Goal, Task, latest failed Attempt, latest Failure, and current trusted diagnosis relationship. It must also prove the request remains current and relevant to the exact recovery source and that no superseding or conflicting action has displaced it.

The existing Task state, graph authority, input correspondence, replacement mapping, meaningful-change, Attempt limit, approval, conflict, optimistic-version, and Event gates remain authoritative. Replanning still requires `TASK_GRAPH_STRUCTURE_INVALID`. Unknown or indeterminate outcomes remain stopped.

## X3. Durable Link and Consumption

Schema version 16 stores one immutable `research_recovery_links` record from the resulting Input Revision or Replanning Decision to the exact request, evidence, accepted decision, Goal, Task, Attempt, Failure, and diagnosis. Exactly one corresponding recovery identity is present. Evidence identity is globally unique in this table, so one evidence record may support at most one recovery action.

Exact replay returns the existing action and link. Identity, content, citation, action-kind, or concurrent-consumption conflict is rejected. Existing Input Revision, Replanning Decision, Research Request, Evidence, Decision, and diagnosis records remain unchanged.

## X4. Runtime and Inspection

The explicit Architecture 2 runtime accepts the optional citation on its existing input-revision and replanning wrappers and exposes read-only linkage inspection by recovery identity. Architecture 1 remains the normal Electron authority.

## X5. Deferred Boundaries

Phase 1S does not authorize autonomous research, research providers, web/model access, automatic evidence acceptance, automatic action selection, background recovery, retries from research, provider qualification, installation, cancellation/preemption, distributed execution, UI work, Electron authority cutover, or generalized planning or policy infrastructure.

## X6. Preserved Safety Controls

Research-assisted actions do not create an Attempt. Any later Attempt remains subject to the existing exact next-number, retry-budget, approval, provider qualification, health, circuit, probe, resource, lease, concurrency, and single-use input-revision controls. Replanning continues to create only inert planned graph work that must pass normal scheduling and execution admission. Passing governed Verification remains the sole Task-success authority. Research cannot convert an indeterminate external outcome into recovery authority or bypass reconciliation. **Unknown means stop.**

## X7. Persistence and Reconstruction

Migration from populated schema version 15 to schema version 16 preserves all existing data and fabricates no linkage or recovery authority. Close/reopen reconstruction must reproduce every linkage exactly. Invalid identifiers, timestamps, target shape, accepted-decision relationship, or Goal/Task/Attempt/Failure/diagnosis attribution must produce explicit corruption diagnostics. SQLite foreign keys, immutable-history triggers, unique constraints, deterministic queries, and the established transaction and concurrency patterns remain required.

## X8. Acceptance Requirements

Controlled implementation must verify accepted evidence supporting valid input revision and valid replanning; recorded, rejected, stale, unrelated, malformed, contradictory, or mismatched evidence rejection; no authority or mutation from research alone; preservation of each action's normal authorization, Attempt-limit, approval, Verification, provider, resource, circuit, lease, and reconciliation gates; indeterminate-outcome rejection; exact replay and conflicting or concurrent use behavior; immutable linkage inspection across restart; corruption diagnostics; populated schema-15 migration without fabricated authority; Phase 1L through 1R regressions; runtime/import regression; complete automated tests; TypeScript validation; production build; Electron startup regression where applicable; diff hygiene; and living-document and engineering-log updates.

All Phase 1R deferred boundaries and all earlier deferrals remain preserved except the narrow accepted-evidence consumption for input revision and replanning expressly authorized here.
