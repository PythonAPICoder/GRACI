# Addendum 023 - Architecture 2 Phase 1R Governed Research Foundation

**Status:** Approved for controlled implementation

**Date:** 2026-08-14

This addendum extends Addendums 005 through 022 and supersedes only the deferment of the narrow caller-invoked research-record foundation below. It does not authorize autonomous research execution, web access, provider invocation, capability discovery, installation, or use of research as execution authority.

## W1. Narrow Authorization

Phase 1R may create one durable Research Request only for an exact current trusted Phase 1L diagnosis with disposition `research_recommended` and outcome certainty `proven_unsuccessful`. The caller supplies a bounded non-empty question, purpose, actor, and canonical UTC time. The request records the exact Goal, Task, failed Attempt, Failure, and diagnosis that establish its context.

Missing, stale, superseded, malformed, contradictory, indeterminate, or otherwise ineligible authority fails closed. The Phase 1N invariant remains absolute: **Unknown means stop.**

## W2. Immutable Records and Derived Lifecycle

Phase 1R introduces three immutable record types:

- `ResearchRequest`, representing explicit caller intent and its exact failure context;
- `ResearchEvidence`, representing information supplied in response to one request;
- `ResearchDecision`, representing one final trusted caller decision to accept or reject one evidence record.

Lifecycle is derived from immutable records: a request begins `requested`, becomes `evidence_recorded` when it has evidence without final decisions, and is represented as `accepted` or `rejected` for decided evidence. Evidence is never updated to encode acceptance. No consumption table is authorized.

## W3. Evidence Contract

Evidence requires a bounded non-empty supplier identity and supplier type, canonical UTC supply time, bounded non-empty source and reference, and bounded finite acyclic plain-JSON object content. Optional integrity metadata, when supplied, is also bounded plain JSON. Credentials, secrets, endpoint details, raw command lines, and unrelated private content are prohibited.

Recording evidence does not accept it, qualify a capability, establish provider or Node health, or authorize execution. External or provider-supplied content remains information rather than authority.

## W4. Final Decision Contract

Each evidence record may receive exactly one immutable final decision: `accepted` or `rejected`, with a bounded non-empty actor and reason and canonical UTC decision time. Equivalent repeated commands may return the existing decision. Conflicting identity, verdict, actor, reason, or time reuse is rejected.

The decision gate is serialized in one SQLite `BEGIN IMMEDIATE` transaction. Conditional writes and uniqueness constraints enforce exactly one final decision under concurrent callers.

## W5. Transactional Authority and Reconstruction

Schema version 15 stores immutable requests, evidence, and decisions with foreign keys to their exact authority chain and audit Events. Request creation reconstructs and revalidates the current Goal/Task/Attempt/Failure/diagnosis chain, trusted diagnosis policy/version, disposition, outcome certainty, and conflict state inside the writing `BEGIN IMMEDIATE` transaction. Pre-transaction inspection is never sufficient authority.

Every record and corresponding Event commits atomically. Close/reopen reconstruction preserves exact identity, attribution, content, actors, reasons, timestamps, and Event relationships. Invalid JSON, identifiers, timestamps, authority relationships, verdicts, or Event correspondence produce explicit corruption diagnostics rather than defaults or inferred state.

## W6. Information-Only Safety Boundary

Accepted research evidence remains information only. Creating, recording, accepting, rejecting, or inspecting research must not mutate or authorize any Goal, Task, Task Graph, Task inputs, Attempt, retry, replanning, approval, provider, capability, qualification, health observation, Node, offering location, resource decision, lease, circuit, or execution state.

Phase 1R creates no automatic follow-up, consumption authority, retry authority, planning authority, qualification authority, installation authority, or provider-selection authority. Any later use of accepted evidence requires separately governed behavior and all normal controls.

## W7. Runtime and Inspection

The explicit Architecture 2 runtime composition boundary exposes caller-invoked APIs to create and inspect requests, record evidence, accept or reject evidence, and inspect accepted evidence. Inspection is deterministic and read-only. Architecture 1 remains the normal Electron startup authority.

## W8. Acceptance Requirements

Controlled implementation must verify bounded request and evidence validation; exact latest trusted failure authority; `research_recommended` plus `proven_unsuccessful` admission; unknown/indeterminate stop behavior; immutable evidence separate from decisions; recording without acceptance; accepted and rejected reconstruction; exactly one final decision under idempotent and conflicting concurrent calls; schema-14 populated migration; SQLite close/reopen reconstruction and corruption diagnostics; information-only non-mutation of all workflow, provider, qualification, health, Node, lease, circuit, and execution authority; runtime APIs; focused tests; TypeScript validation; diff hygiene; living-document and engineering-log updates.

## W9. Deferred Boundaries

Phase 1R does not authorize research-provider execution, web or model research, browser or network tools, autonomous request creation, background research, source fetching, automatic evidence acceptance, evidence consumption, planning or replanning from evidence, Task or Goal mutation, input revision, retry or recovery, capability discovery, provider registration, qualification, health mutation, Node mutation, installation, generalized tool execution, memory promotion, UI work, Electron Architecture 2 authority cutover, distributed workers, or multiple Orchestrators.

All Phase 1Q deferred boundaries and all earlier deferrals remain preserved except the narrow governed research-record foundation expressly authorized here.
