# G.R.A.C.I. Engineering Decision Log

### DEC-0022 - Phase 1U Immutable Scoped Working Memory

- **Date:** 2026-08-14
- Store bounded plain-JSON memory separately from canonical workflow and research records; creation is always explicit.
- Use exact Goal scope or reusable scope with a durable permission rationale, explicit reusable retrieval inclusion, and deterministic `asOf` filtering/order.
- Represent correction as an immutable same-scope successor under `BEGIN IMMEDIATE`; never rewrite or delete history.
- Preserve provenance and explicit trust status while granting memory no execution, recovery, policy, acceptance, provider, resource, or Verification authority.

### DEC-0021 - Phase 1T Separate Research Execution Authority

- **Date:** 2026-08-14
- Keep Research Request execution separate from canonical Task Attempts and reuse the existing provider resolver, qualification, health, and offering-circuit filters.
- Persist one schema-17 execution per request before invocation, bound to the exact resolution, Provider, offering, contract version, and idempotency key.
- Atomically finalize success with unaccepted Phase 1R evidence or finalize a bounded known/indeterminate failure without retry or recovery authority.

### DEC-0020 - Phase 1S Exact Research Support Linkage

- **Date:** 2026-08-14
- Extend the existing Phase 1P and Phase 1Q commands with an optional exact Research Evidence citation rather than creating parallel recovery commands.
- Admit `research_recommended` only when the cited evidence has an accepted decision and the complete request/evidence/source chain is current and exact inside the action transaction.
- Store one generic immutable schema-16 link with a closed action kind and exactly one recovery foreign key; make evidence globally unique so concurrent or cross-action reuse fails closed.
- Preserve every normal action gate and every existing authority record; evidence supports but never independently executes or authorizes an action.

### DEC-0019 - Phase 1R Failure-Scoped Governed Research Records

- **Date:** 2026-08-14
- Scope request creation to the exact current trusted `research_recommended` and `proven_unsuccessful` Phase 1L diagnosis chain.
- Store immutable requests, supplier evidence, and one separate accepted/rejected decision per evidence in schema 15; derive lifecycle and create no consumption table.
- Revalidate request authority and serialize final decisions inside `BEGIN IMMEDIATE`.
- Treat accepted evidence as information only, with no workflow, routing, qualification, health, resource, recovery, or execution authority.

### DEC-0018 - Phase 1Q Governed Replanning

- **Date:** 2026-08-14
- Use only exact trusted `TASK_GRAPH_STRUCTURE_INVALID` / `replanning_recommended` authority.
- Store immutable lineage and normalized replacement mappings in schema 14.
- Atomically validate, admit, supersede, and activate under `BEGIN IMMEDIATE`; historical revisions are inspection-only.
- Preserve completed and evidence-bearing history; reject in-flight, approval-bound, conflicting, stale, ambiguous, and indeterminate work.

Use this log for decisions that matter but do not yet justify a dedicated ADR system.

## Entry Template

### DEC-XXXX — <Decision Title>

**Date**

- YYYY-MM-DD

**Context**

- 

**Decision**

- 

**Alternatives Considered**

- 

**Rationale**

- 

**Consequences**

- 

**Revisit Trigger**

- Repeated verification/reporting failures by GLM-4.7-Flash
- Sustained poor task-completion performance
- A materially stronger local coding-agent model becoming available
- Future scheduled capability requalification

---

### DEC-0017 - Phase 1P Governed Task Input Revision

**Date**

- 2026-08-14

**Decision**

- Authorize only caller-invoked revision of canonical Task inputs for the exact current Phase 1L `input_revision_required` diagnosis with `proven_unsuccessful` outcome certainty.
- Require a canonically meaningful plain-JSON change while preserving every prior Attempt snapshot and all immutable history.
- Reconstruct the complete authority, approval, Attempt-limit, conflict, input-correspondence, mutation, and Event gates inside the writing `BEGIN IMMEDIATE` transaction.
- Bind durable authority to the exact next Attempt number and full revised input snapshot, consuming it atomically once while preserving every normal execution and Verification control.
- Preserve the absolute rule that unknown external outcomes stop and cannot use input revision.

**Rationale**

- Correctable Task data should be replaceable without rewriting failed execution history, weakening concurrent authority checks, or creating a parallel retry system.

**Consequences**

- Schema version 13 stores immutable input revisions and single-use Attempt consumption.
- Goal, Task structure, graph revision, replanning, automatic repair, research, UI, and Electron authority cutover remain deferred.

---

### DEC-0016 - Phase 1O Scoped Circuit Breakers and Consumable Bound Probes

**Date**

- 2026-08-14

**Decision**

- Authorize independent circuits for provider offerings, Nodes, and offering locations with explicit `closed`, `open`, and `half_open` states.
- Count only current trusted Phase 1L `proven_unsuccessful` diagnoses in a versioned deterministic observation window; exclude input, policy, Verification, indeterminate, cancellation, and unknown categories.
- Keep cooldown deterministic and require one durable active probe to pass a half-open route.
- Make probe authority consumable: claim it once against the exact provider/resource decision and exact Task/Attempt/offering/Node/location binding, then revalidate it atomically at Attempt start.
- Permit only a persisted passing normal Verification for the bound successful Attempt to close; a current qualifying diagnosis for the bound failed Attempt reopens.
- Keep circuit state separate from health, qualification, Node administration, location enablement, workstation evidence, and leases; grant no replay or replacement authority.

**Rationale**

- Repeated known failures should suppress unhealthy routes without converting health observations or provider self-report into lifecycle authority. Durable exact binding prevents a half-open authorization from becoming a reusable routing bypass.

**Consequences**

- Schema version 12 stores circuit state, immutable evidence/transitions, and durable probe claim/consumption history.
- Provider and resource routing expose stable scope-specific circuit explanations.
- Unknown means stop remains unchanged, and every prior deferral except circuit breakers/half-open probes remains in force.

---

### DEC-0015 - Phase 1N Provider-Neutral External Outcome Reconciliation

**Date**

- 2026-08-14

**Decision**

- Reconcile only the exact current indeterminate Attempt through a caller-invoked provider-neutral evidence boundary.
- Keep lifecycle authority in trusted core and permit only `proven_completed`, `proven_not_completed`, or `remains_indeterminate`.
- Route proven completion through normal Verification without a replacement Attempt.
- Persist proven non-completion regardless of retry authority, granting single-use next-Attempt authority only when existing Attempt and approval gates permit it.
- Keep remaining uncertainty stopped and prohibit conflicting conclusive authority.

**Rationale**

- External evidence can resolve uncertainty without allowing providers to declare success or bypass existing retry, approval, resource, and Verification controls.

**Consequences**

- Schema version 11 stores immutable reconciliation evidence, decisions, and exact Attempt or Verification consumption relationships.
- Reconciliation remains explicit; no startup, background, or scheduler polling is introduced.

---

### DEC-0014 — Phase 1M Single-Use Alternative Recovery

**Date**

- 2026-08-14

**Decision**

- Authorize only caller-invoked execution of `alternative_offering_recommended` and `alternative_node_recommended`.
- Persist one immutable recovery decision per authoritative diagnosis and atomically record changed-condition evidence before returning the Task to `ready`.
- Exclude the failed offering, Node, and location explicitly through the existing deterministic resolver and scheduler.
- Count every alternative against the existing total Attempt limit and consume an authorization only through its exact next Attempt binding.
- Keep indeterminate outcomes, reconciliation, replanning, research, migration, cancellation, circuit breakers, UI, and distributed execution deferred.

**Rationale**

- Phase 1L supplies durable authoritative diagnosis, while existing provider qualification, Node health, resource leases, Attempts, and Verification supply the minimum safe foundation for bounded alternatives without introducing a generalized recovery engine.

**Consequences**

- Alternative offering execution resolves the adapter by the durably selected offering.
- Alternative Node execution retains normal atomic resource scheduling and lease rules.
- A failed recovery Attempt returns through the normal Failure and Phase 1L diagnosis path.

---

### DEC-0013 — Phase 1L Durable Failure Diagnosis Boundary

**Date**

- 2026-08-14

**Decision**

- Approve Addendum 017 for controlled future implementation of deterministic, durable failure diagnosis and exactly one bounded recovery disposition.
- Keep cause, outcome certainty, retryability, and disposition separate, and require missing or malformed evidence to fail closed.
- Preserve existing Attempt limits, opt-in verification retry, approval semantics, conservative indeterminate-outcome handling, and Phase 1K independent supervision.
- Require small factual changed-condition evidence before a non-transient future Attempt could be authorized, without introducing generalized cost, elapsed-time, risk-budget, or policy infrastructure.
- Treat alternative, reconciliation, approval, replanning, and research dispositions as recommendations only; authorize no automatic advanced recovery action.

**Rationale**

- Existing durable Attempts, Failures, Verifications, provider and Node bindings, retry policy, and audit history provide sufficient evidence for a bounded diagnosis layer. Durable judgment must precede circuit breakers, alternative execution, replanning, and research so later recovery cannot become blind replay or provider-authored authority.

**Consequences**

- Phase 1L is implemented as the latest verified Architecture 2 phase.
- Diagnosis authority is unique per `(Failure ID, diagnosis policy ID, policy version)` and uses a deterministic SHA-256-derived diagnosis ID plus evidence fingerprint.
- Every new Orchestrator Failure is diagnosed in its existing atomic lifecycle transaction; migration does not fabricate diagnoses for historical Failures, which remain explicitly diagnosable.
- Failover, alternate-Node retry, cancellation, circuit breakers, reconciliation execution, replanning, research, distributed execution, and Electron authority changes remain unauthorized.

---

### DEC-0012 — Phase 1K Bounded Concurrent Scheduling

**Date**

- 2026-08-14

**Decision**

- Approve caller-configured positive-integer `maxConcurrentTasks`, defaulting to one.
- Admit ready Tasks in the existing `createdAt`, then Task-ID order while allowing independent admitted Tasks to overlap.
- Keep resource-unavailable Tasks ready without an Attempt or retry charge and continue scanning later ordered Tasks.
- Atomically persist resource scheduling, lease acquisition, and `ready -> scheduled` when resource routing is used.
- Use independent settled supervision and reject overlapping `run()` calls on one Orchestrator.
- Keep runtime slots process-local and use existing capacity leases for effective exclusivity; add no queue, lock service, worker layer, or schema migration.

**Rationale**

- Provider, node, lease, and workstation safeguards established through Phase 1J are sufficient for bounded single-process concurrency. Preserving canonical Task state and transactional capacity enforcement adds concurrency without weakening dependency, recovery, approval, retry, or audit semantics.

---

### DEC-0011 — Phase 1J Evidence-Linked Workstation Policy Application

**Date**

- 2026-08-13

**Decision**

- Approve explicit application of one persisted Phase 1I recommendation with exact Node state/version expectations.
- Represent policy ownership by linking immutable application decisions to administrative transition history.
- Permit reactivation only when the current draining version was produced by the same policy identity/version.
- Record rejected and no-change decisions durably; keep the scheduler, leases, Attempts, and Electron authority unchanged.

**Rationale**

- Durable ownership and optimistic concurrency prevent workstation recommendations from reversing manual or newer administration while allowing safely attributable drain/reactivation behavior.

---

### DEC-0007 — Phase 1F Capability and Provider Resolution Boundary

**Date**

- 2026-08-13

**Context**

- Phase 1E completed the explicit Architecture 2 runtime composition and non-canonical legacy-state import boundary.
- Addendum 005 places durable capability/provider resolution before multi-node resource scheduling.
- The current Architecture 1 registries and Ollama singleton are prototypes, not qualified Architecture 2 contracts.

**Decision**

- Approve Addendum 011 for controlled implementation of Architecture 2 Slice 2 as Phase 1F.
- Persist versioned providers, capabilities, offerings, qualifications, health observations, and routing decisions with append-only audit history.
- Require deterministic policy-filtered resolution and record the selected offering before invocation.
- Adapt Ollama behind a caller-configured Model Provider boundary and require explicit qualification before resolver eligibility.
- Keep node/resource scheduling, cloud providers, generalized policy, UI integration, and Architecture 2 Electron authority deferred.

**Alternatives Considered**

- Extend the Architecture 1 in-memory registries.
- Treat Ollama availability or model inventory as automatic qualification.
- Combine provider resolution with multi-node scheduling and failover.
- Make Architecture 2 the default Electron runtime during provider integration.

**Rationale**

- Durable evidence and deterministic resolution preserve the capability-first design without coupling core workflow to Ollama or a node topology.
- Separating provider selection from future resource scheduling keeps Slice 2 independently testable and respects roadmap dependency order.
- Explicit qualification prevents discovered or merely healthy components from being treated as production-ready.

---

### DEC-0008 — Phase 1G Durable Node Binding Boundary

**Date**

- 2026-08-13

**Decision**

- Approve Addendum 012 for controlled implementation of the smallest Architecture 2 Slice 3 node-binding and lease kernel.
- Keep offering resolution separate from deterministic node/location selection.
- Require durable health evidence, scheduling explanations, capacity-aware leases, and matching Attempt bindings before invocation.
- Preserve sequential execution and defer discovery, telemetry, concurrency, preemption, gaming detection, and automatic failover.

**Rationale**

- Durable identity and leases are prerequisites for safe multi-node execution. Extending the Architecture 1 in-memory registry or introducing concurrency first would create unprovable health, ownership, and recovery behavior.

---

### DEC-0009 — Phase 1H Configured Node Inspection Boundary

**Date**

- 2026-08-13

**Decision**

- Approve explicit, bounded inspection of registered Ollama Nodes and durable sanitized inspection evidence.
- Approve auditable manual Node administrative-state transitions with stale-write protection.
- Keep inventory evidence inert and defer discovery, polling, telemetry, concurrency, and automatic failover.

**Rationale**

- Resource scheduling requires current truthful observations, but automated discovery and control policies should not be introduced before explicit configured-node behavior is durable and verifiable.

---

### DEC-0010 — Phase 1I Workstation Availability Recommendation Boundary

**Date**

- 2026-08-13

**Decision**

- Approve bounded caller-invoked Windows process snapshots and deterministic exact-basename workload rules.
- Persist recommendations as evidence while requiring a separate explicit manual Node transition to apply them.
- Prohibit command-line capture, background monitoring, automatic drain/reactivation, and process control.

**Rationale**

- This satisfies the initial workstation-protection dependency, including Mod Organizer 2 awareness, without allowing observational evidence to become autonomous administrative authority.

**Consequences**

- The provider execution contract and Orchestrator binding must evolve so the exact offering is selected and persisted before invocation.
- Architecture 1 remains active and its registry state remains unsupported compatibility input.
- Multi-node and resource-aware scheduling remain Phase 1F non-goals.

**Revisit Trigger**

- Phase 1F acceptance evidence is complete and Slice 3 planning begins.
- A provider requires authoritative reconciliation, streaming, multimodal behavior, or a materially different invocation contract.

---

### DEC-0006 — Preserve Importable Architecture 1 Tasks as Non-Canonical History

**Date**

- 2026-08-13

**Context**

- Architecture 1 lifecycle records do not contain Architecture 2 execution, verification, dependency, approval, or qualification evidence.
- Phase 1E requires deterministic, idempotent, provenance-aware import without making Architecture 2 authoritative.

**Decision**

- Assess exact source bytes independently of the Architecture 1 state cache and fallback loader.
- Preserve only structurally complete legacy Task records in immutable, non-canonical history tables.
- Keep registry records unsupported and never promote them to qualified Architecture 2 components.
- Use the source SHA-256 digest as the import-operation idempotency identity and `(source digest, section, key)` as the record uniqueness boundary.
- Compose Architecture 2 only through an explicit caller-configured runtime factory; do not wire it into Electron startup.
- Require callers to supply the execution provider and verifier explicitly; deterministic test components have no production composition default.

**Alternatives Considered**

- Convert legacy `completed` Tasks to canonical `succeeded` Tasks.
- Create draft Goals and canonical Tasks from incomplete legacy semantics.
- Preserve import data only in audit event payloads.
- Automatically assess or import during Electron startup.

**Rationale**

- A dedicated inert history boundary preserves useful provenance while making fabricated lifecycle evidence structurally impossible.
- Durable uniqueness provides restart-safe idempotency without modifying the source file.
- Explicit composition enables integration testing while preserving Architecture 1 authority.

**Consequences**

- Imported history is inspectable but not schedulable or executable.
- Future promotion into canonical workflow state requires new governance and explicit semantics.
- Phase 1F provider/capability work remains deferred.

**Revisit Trigger**

- A governed phase defines evidence-safe promotion semantics or replaces Architecture 1 as the active runtime.

---

### DEC-0005 — Phase 1D Persisted Task Queue and Deterministic Admission

**Date**

- 2026-08-13

**Context**

- Architecture 2 already persists canonical Tasks, immutable dependency edges, Attempts, Failures, approvals, and audit events in SQLite.
- Phase 1D requires durable queue behavior, complete dependency validation, deterministic selection, and inspectability without introducing parallel workflow authority.

**Decision**

- Persisted canonical Tasks and their lifecycle states are the durable queue.
- Admit a complete Task Graph Revision, Tasks, dependencies, and structural events atomically after deterministic validation.
- Validate acyclicity with deterministic Kahn processing; cyclic rejection reports sorted unresolved Task IDs, not asserted exact cycle members.
- Select only `ready` Tasks by persisted `createdAt`, then ASCII Task ID lexical order.
- Keep predicate dependencies waiting and inspectable; do not execute predicates in Phase 1D.
- Preserve conservative scheduled/running restart failure without automatic replay or an exactly-once claim.

**Alternatives Considered**

- A separate queue table or queue-item model.
- An in-memory or external broker as queue authority.
- Priority-first scheduling.
- Exact strongly connected component diagnostics.
- Automatic replay of interrupted work.

**Rationale**

- The existing Task schema and SQLite kernel already hold the required authoritative state.
- Complete admission prevents partially visible executable graphs.
- Explicit stable ordering and pure graph validation make results reproducible across reconstruction and input permutations.
- Conservative recovery avoids duplicating uncertain external effects.

**Consequences**

- Architecture 1 remains disconnected.
- Scheduling remains sequential and resource-neutral.
- Predicate execution, resource/node routing, concurrent scheduling, and provider reconciliation remain future governed work.

**Revisit Trigger**

- An approved phase introduces dynamic replanning, predicate evaluation, concurrent resource scheduling, or provider-specific reconciliation.

---

### DEC-0003 — Phase 1C Conservative Retry Policy

**Date:** 2026-08-13

**Decision**

- Use three total Attempts by default, derived from persisted Attempt history.
- Automatically retry only `transient`; permit `verification_failed` retry only through `retryPolicy.retryVerificationFailures: true`.
- Never automatically retry `permanent`, `approval_required`, or `external_outcome_indeterminate`.
- Retain the existing diagnostic Failure category and add the smaller policy classification separately.

**Rationale**

- This preserves Phase 1B diagnostics while preventing uncertainty or verification rejection from becoming unsafe replay.

**Acceptance correction**

- Durable `retry_pending` status is not sufficient authorization by itself; recovery revalidates the latest relevant Failure, explicit retryability, classification policy, and remaining budget.
- Schema-1 migration maps only retryable `transient_infrastructure` to `transient`. Ambiguous `resource_unavailable` and `policy_or_approval` records map to `permanent`; verification and indeterminate meanings remain explicit.

---

### DEC-0004 — Phase 1B Interrupted Execution Fails Closed Without Replay

**Date**

- 2026-08-12

**Context**

- Addendum 005 requires restart reconciliation and forbids blind replay of consequential work.
- Phase 1B has no provider-specific reconciliation, retry engine, or idempotency policy.
- A persisted running Attempt after process restart has an unknown external outcome.

**Decision**

- Recover a persisted running Attempt as terminal `indeterminate`, record a non-retryable `external_outcome_indeterminate` Failure, and transition its Task to `failed` atomically.
- Never automatically execute that Task again in Phase 1B.
- Fail explicitly if a running Task lacks its required persisted running Attempt.

**Alternatives Considered**

- Mark the Task succeeded without evidence.
- Automatically rerun the Task.
- Leave it indefinitely running without a recorded diagnosis.

**Rationale**

- The selected behavior preserves truth, prevents duplicate side effects, and implements the safe `marked failed` recovery disposition explicitly allowed by Addendum 005 E16.

**Consequences**

- Manual or future policy-driven recovery is required for interrupted work.
- Later providers may introduce authoritative reconciliation and idempotent retry through a new approved phase.

**Revisit Trigger**

- A provider supplies reliable outcome reconciliation or checkpoint/resume.
- A retry/idempotency policy is approved.

---

### DEC-0003 — Architecture 2 Phase 1A SQLite Kernel

**Date**

- 2026-08-12

**Context**

- Product Owner and Architect approved controlled implementation of only the durable domain and persistence kernel.
- System Node v24.19.0 and Electron's embedded Node v24.18.1 both expose the built-in `node:sqlite` `DatabaseSync` API.
- The repository already contains `sql.js`, but Phase 1A requires restart-safe native SQLite behavior and prohibits adding another persistence dependency without approval.

**Decision**

- Use built-in `node:sqlite`; add no dependency.
- Implement Architecture 2 in an isolated `src/architecture2` module with a provider-independent persistence contract.
- Use SQLite schema migration version 1, relational current state, atomic state-plus-event transactions, and a deterministic SHA-256 event hash chain.
- Keep Architecture 1 intact and disconnected from the new kernel in this phase.

**Alternatives Considered**

- `sql.js`, which uses an in-memory/WebAssembly database image and would require separate durability management.
- `sqlite3`, `better-sqlite3`, an ORM, or a database server; all would add unauthorized dependencies or operational complexity.
- Full event sourcing, which is explicitly outside the approved architecture.

**Rationale**

- `node:sqlite` is present in both production and test runtimes and its TypeScript declarations are already provided by the installed Node types.
- SQLite supplies transactions, foreign keys, strict tables, constraints, and restart-safe local storage without dependency or configuration changes.
- Isolation preserves current application behavior while establishing the new durable contract.

**Consequences**

- Runtime composition and migration from the Architecture 1 JSON store remain future work.
- The SQLite database path must be supplied by the caller; no machine-specific default is introduced.
- Applications packaged against a different Node/Electron runtime must requalify `node:sqlite` compatibility.

**Revisit Trigger**

- Electron or Node runtime changes remove or materially alter `node:sqlite`.
- Measured concurrency or deployment requirements exceed the approved single-runtime SQLite design.
- A later governance addendum authorizes a different persistence provider.

---

### DEC-0002 — Architecture 2 Foundation Proposed as a Durable Modular Monolith

**Date**

- 2026-08-12

**Context**

- The current Electron/TypeScript foundation contains useful prototypes but lacks durable Goal/Task orchestration, transactional state transitions, evidence-based completion, scoped approvals, and restart-safe execution.
- Architecture 2 must remain provider-independent and support multiple local compute nodes without premature distributed-system complexity.

**Decision**

- Propose `ADDENDUM_005_ARCHITECTURE_2_FOUNDATION.md` as the authoritative Architecture 2 design for Product Owner and Architect review.
- Begin future implementation with a durable workflow kernel in a modular monolith, using explicit provider boundaries and an append-only audit/event history.
- Treat current task, state, and registry implementations as compatibility/prototype code rather than Architecture 2 contracts.

**Alternatives Considered**

- Extend the current in-memory task manager and JSON store incrementally without redefining domain semantics.
- Begin with distributed services or adopt a vendor-specific agent/workflow framework.
- Implement memory or broad autonomous planning before durable workflow and verification foundations.

**Rationale**

- A modular monolith minimizes operational complexity while preserving replaceable boundaries.
- Durable attempts, verification, approvals, and events directly address governance requirements for evidence, recovery, and auditability.
- Capability-first contracts prevent Ollama, a particular LLM, or a particular node from becoming a permanent core dependency.

**Consequences**

- Architecture 2 implementation remains paused pending review.
- Persistence engine and other explicitly listed technology choices remain unresolved until qualification during the relevant implementation slice.
- The smallest future implementation slice is the durable workflow kernel described in Addendum 005.

**Revisit Trigger**

- Product Owner or Architect review changes the domain model or implementation sequence.
- Qualification shows the modular-monolith boundary cannot satisfy required durability or concurrency.
- Multi-runtime high availability becomes an approved near-term requirement.

---

### DEC-0001 — Provisional Implementation Engineer Selection

**Date**

- 2026-08-10

**Context**

- Local coding-agent qualification bake-off completed for four candidates
- Task required extending Ollama integration with read-only `/api/tags` model-inventory support
- Independent verification executed for each candidate
- Current development stage requires qualified agent for implementation work

**Decision**

- GLM-4.7-Flash is selected as the provisional G.R.A.C.I. Implementation Engineer.
- This designation is operational and provisional, not a permanent architectural dependency.
- Agent self-reported completion or verification is non-authoritative.
- Executable verification remains authoritative: validation -> tests -> build -> runtime/integration verification when applicable.
- Independent Architect/Reviewer verification remains required during the current development stage.

**Alternatives Considered**

- Qwen3-Coder 30B: failed verification due to reporting integrity issues and incomplete recovery
- Qwen3.6 27B: failed due to task-continuity and goal-retention failures
- GPT-OSS 20B: failed due to inability to complete and verify multi-step implementation

**Rationale**

- GLM-4.7-Flash successfully implemented client, service, public export, and automated tests with correct TypeScript syntax, passing all validation, tests, and build checks.
- Other candidates failed verification across functional correctness, implementation completion, test execution, reporting integrity, or task continuity.

**Consequences**

- Phase 2.2 implementation work will use GLM-4.7-Flash as the current Implementation Engineer.
- Model performance will continue to be measured during real G.R.A.C.I. work.
- A successful qualification does not remove independent verification requirements.
- All qualification results and executive decisions are recorded in TEST_LOG.md and DECISION_LOG.md.

**Revisit Trigger**

- Repeated verification/reporting failures by GLM-4.7-Flash
- Sustained poor task-completion performance
- A materially stronger local coding-agent model becoming available
- Future scheduled capability requalification
