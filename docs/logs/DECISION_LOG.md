# G.R.A.C.I. Engineering Decision Log

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
