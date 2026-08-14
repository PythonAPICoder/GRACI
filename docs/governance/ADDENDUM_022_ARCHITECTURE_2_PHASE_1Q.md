# Addendum 022 - Architecture 2 Phase 1Q Governed Replanning Foundation

**Status:** Approved for controlled implementation

**Date:** 2026-08-14

This addendum extends Addendums 005 through 021 and supersedes only the deferment of caller-invoked Task Graph revision mechanics. Autonomous planning, model-authored planning, and automatic replanning remain deferred.

## V1. Authorization

Phase 1Q may execute only an exact current trusted diagnosis with disposition `replanning_recommended`, outcome `proven_unsuccessful`, and Failure code `TASK_GRAPH_STRUCTURE_INVALID`. The caller supplies a complete replacement graph, explicit replacement mappings, reason, actor, and time. No Planner or provider may manufacture authority.

## V2. Immutable Revision and Replacement

Replanning creates the next immutable Task Graph Revision for the same Goal. Historical revisions, Tasks, Attempts, Failures, diagnoses, Verifications, approvals, Events, and recovery evidence are never rewritten. Completed, failed, cancelled, and already-superseded Tasks retain their historical state. Every unfinished Task in the authoritative source revision must appear exactly once in an unambiguous mapping to one or more Tasks in the replacement revision.

Only `planned`, `blocked`, `ready`, `waiting_for_approval`, and `retry_pending` Tasks may be superseded. Scheduled, running, and verifying work cannot be replaced. A pending approval cannot be bypassed through replacement.

## V3. Validation and Atomic Authority

The complete replacement graph must pass existing deterministic validation. Invalid dependencies, cycles, dangling or duplicate mappings, wrong-Goal revisions, stale revisions, and skipped revision numbers fail closed.

Inside one SQLite `BEGIN IMMEDIATE` transaction, persistence revalidates the Goal's active revision/version, latest Task/Attempt/Failure/diagnosis chain, diagnosis policy/version, conflicting recovery, replacement scope, graph structure, and Events. It then admits the graph, records immutable decision/mappings, supersedes eligible old Tasks, and changes the Goal's active revision. Failure rolls back all writes. Optimistic concurrency and SQLite write serialization ensure competing replans cannot both activate.

## V4. Execution and Safety

Only the Goal's authoritative revision may use the normal Orchestrator path. Replacement Tasks receive no automatic execution, Attempt, approval, provider, resource, circuit, lease, or Verification waiver. Attempt history and limits are never reset. Only normal passing Verification produces Task success.

The Phase 1N invariant remains absolute: **Unknown means stop.** Indeterminate external outcomes require reconciliation and cannot authorize replanning, replacement, replay, retry, rerouting, migration, or inferred success.

## V5. Persistence and Inspection

Schema version 14 stores immutable replanning decisions and normalized superseded-to-replacement Task relationships. Runtime inspection exposes the Goal active revision, revision lineage, and decisions. Migration from schema 13 preserves existing data and fabricates no replanning authority.

## V6. Deferred Boundaries

Phase 1Q does not authorize autonomous or LLM-generated planning, automatic replanning, governed research, discovery or installation, background recovery, cancellation/preemption, checkpoint migration, distributed orchestration, UI/Electron integration, generalized policy redesign, or unrelated refactoring.
