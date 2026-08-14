# Addendum 025 - Architecture 2 Phase 1T Governed Research Provider Execution

**Status:** Approved for controlled implementation

**Date:** 2026-08-14

This addendum extends Addendums 005 through 024 and supersedes only the Phase 1R and Phase 1S prohibition on the narrow caller-invoked research-provider execution below. All other deferred behavior remains unauthorized.

## Y1. Narrow Execution Boundary

Phase 1T may execute one existing valid Research Request through one eligible qualified provider offering of the requested research capability. Execution is explicitly caller-invoked and bounded. It creates no background loop, autonomous research plan, browser/search integration, provider installation, discovery, or vendor-specific trusted-core dependency.

## Y2. Provider Resolution and Binding

Execution must use the existing deterministic provider resolver. Contract, capability, qualification, health freshness, privacy, permission, format, schema, feature, quality, latency, cost, side-effect, and provider-offering circuit gates remain authoritative. The exact resolution decision, Provider, offering, contract version, and idempotency key are persisted before invocation. Runtime adapters are caller-supplied and must match the selected durable Provider and offering exactly.

No eligible offering means no provider invocation. Phase 1T does not silently weaken constraints, switch providers, retry, probe, install, qualify, or mutate health.

## Y3. Current Research Authority

Inside the execution-start `BEGIN IMMEDIATE` transaction, persistence must revalidate the exact Research Request, Goal, failed Task, latest failed Attempt, latest Failure, and current trusted `research_recommended` plus `proven_unsuccessful` diagnosis. Stale, superseded, malformed, contradictory, indeterminate, mismatched, or already-executed authority fails closed.

Each Research Request may create at most one provider execution. Concurrent duplicate callers serialize through SQLite and only one may obtain invocation authority.

## Y4. Result and Failure Semantics

A successful provider result is recorded atomically as immutable Phase 1R Research Evidence and a terminal provider-execution result. Evidence records the exact Provider and offering through the execution relationship and remains unaccepted until the existing final acceptance command explicitly accepts it.

Retryable and non-retryable provider failures are normalized into durable bounded execution failure evidence. Provider exceptions are non-retryable execution failures. An indeterminate provider outcome is recorded as `external_outcome_indeterminate`, creates no Research Evidence, and grants no replay, retry, alternative, recovery, or acceptance authority. **Unknown means stop.**

No provider result may mutate a Goal, Task, Task inputs, graph, Attempt, approval, recovery, qualification, health record, Node, lease, circuit, Verification, or acceptance decision.

## Y5. Persistence, Reconstruction, and Runtime

Schema version 17 stores one durable research-provider execution per Research Request, linked to its exact provider-resolution decision, Provider, offering, optional resulting Research Evidence, failure semantics, idempotency key, timestamps, and audit Events. Start authority and Event commit atomically before invocation. Known completion and its evidence or failure Event commit atomically after invocation.

Terminal execution records cannot be rewritten or deleted. A persisted running execution after restart is uncertain stopped history and is never automatically replayed. Close/reopen inspection reconstructs exact execution provenance and status. Migration from populated schema 16 preserves all prior data and fabricates no execution history.

The explicit Architecture 2 runtime exposes only caller-invoked execution and read-only execution-history inspection. Architecture 1 remains the normal Electron authority.

## Y6. Preserved Safety Controls

Phase 1T does not accept evidence, revise inputs, replan, execute recovery, bypass approval, bypass qualification or health, bypass provider circuits, bypass Node/resource rules where applicable, create a Task Attempt, consume retry budget, or replace Verification. Existing Phase 1R acceptance and Phase 1S recovery citation remain separate explicit actions.

## Y7. Acceptance Requirements

Controlled implementation must verify eligible qualified execution; ineligible and unqualified rejection; open-circuit rejection; exact Provider/offering/resolution provenance; evidence remaining unaccepted; durable provider failure and indeterminate stop behavior; no automatic recovery; stale request rejection; restart reconstruction; concurrent duplicate exclusion; populated schema-16 migration; Phase 1R/1S, provider, circuit, recovery, persistence, runtime/import, and Electron regressions; TypeScript validation; full tests; production build; and diff hygiene.

## Y8. Deferred Boundaries

Phase 1T does not authorize unrestricted web browsing, search-engine integration, direct vendor integration, autonomous research planning, automatic evidence acceptance, automatic input revision or replanning, retries or provider switching, provider/node probing, model discovery/download, installation, generalized memory/RAG, background agents, distributed execution, UI/Electron integration, or unrelated refactoring.
