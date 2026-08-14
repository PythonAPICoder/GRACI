# Addendum 017 — Architecture 2 Phase 1L Durable Failure Diagnosis and Recovery Disposition

**Status:** Approved for controlled implementation

**Date:** 2026-08-14

This addendum extends Addendums 005 through 016 and authorizes only a deterministic, auditable, restart-safe failure-diagnosis and recovery-disposition layer. Phase 1L establishes the judgment foundation for later recovery capabilities; it does not authorize those recovery actions.

## Q1. Diagnosis Boundary

For each relevant persisted Failure, Architecture 2 must produce at most one current diagnosis operation and exactly one immutable, attributable, versioned diagnosis result. The result answers, from durable evidence: what failed, why it failed, the certainty of the external outcome, and the one permitted recovery disposition.

Diagnosis must be deterministic trusted-core behavior. Provider or LLM self-report may be retained as untrusted evidence but cannot authoritatively determine the cause, outcome certainty, retryability, or disposition.

## Q2. Attribution and Evidence

Each diagnosis must identify its Task and Failure and, when applicable and available, the relevant Attempt, provider offering, Provider, compute Node, offering location, routing decision, resource decision, Verification, Approval, and other bounded evidence references. Absence of optional attribution is not fabricated.

Diagnosis evidence must be sanitized and bounded. Credentials, secrets, endpoint details, raw command lines, and unrelated private content remain prohibited. Missing, malformed, corrupt, contradictory, or insufficient authoritative evidence fails closed with an explicit diagnostic reason and a non-executing disposition.

## Q3. Distinct Diagnostic Concepts

Cause, outcome certainty, retryability, and recovery disposition are separate governed concepts and must not be inferred from one another without an explicit rule.

Cause classification must be deterministic and compatible with the existing Failure categories, including transient infrastructure, resource unavailability, provider or capability mismatch, invalid input or precondition, policy or approval, execution defect, verification failure, external outcome indeterminate, cancellation or preemption evidence when later authorized, and unknown cause.

Outcome certainty is represented independently and must distinguish at least a proven completed outcome, a proven unsuccessful outcome, an indeterminate external outcome, and insufficient or malformed evidence. Retryability remains subject to existing Phase 1C retry policy and durable Attempt history.

## Q4. Recovery-Disposition Vocabulary

Each diagnosis selects exactly one disposition from this bounded vocabulary:

- `terminal_failure`
- `retry_same_path`
- `alternative_offering_recommended`
- `alternative_node_recommended`
- `reconciliation_required`
- `approval_required`
- `input_revision_required`
- `replanning_recommended`
- `research_recommended`

Only `retry_same_path` may authorize an ordinary Phase 1L retry, and it does so only when the existing retry policy, Failure classification, retryability evidence, and remaining Attempt limit already permit that retry. Every other disposition is diagnostic or advisory and does not execute the named recovery behavior.

`external_outcome_indeterminate` must fail closed with `reconciliation_required`. It cannot authorize replay, same-path retry, alternative offering execution, alternative Node execution, inferred success, or terminal cancellation.

## Q5. Changed-Condition Evidence and Retry

A changed condition is a small immutable factual record linked to the diagnosis and sufficient to explain why a later Attempt could differ. It identifies the relevant condition type, prior fact or bounded reference, changed fact or bounded reference, source, and UTC observation time. It is not a policy rule, plan revision, health mutation, or generalized recovery engine.

Blind identical retry remains forbidden except for a demonstrably transient failure authorized by the existing retry policy and remaining Attempt limit. A non-transient diagnosis cannot authorize another Attempt without relevant factual changed-condition evidence and a later phase that authorizes the corresponding recovery action. Phase 1L does not introduce generalized cost, elapsed-time, or risk-budget infrastructure.

Verification-failure retry remains opt-in through the existing Task retry policy. Diagnosis cannot broaden retry classifications, reset Attempt history, increase retry limits, or bypass approval. A diagnosis of `approval_required` is advisory and does not create a new Approval request solely because diagnosis selected that disposition.

## Q6. Durability, Inspection, and Reconstruction

Diagnosis records, dispositions, changed-condition evidence, and their audit Events are immutable history. Repeated diagnosis of equivalent persisted authoritative evidence under the same diagnosis policy/version must return the existing result or produce an equivalent deterministic result without conflicting duplicate authority.

Architecture 2 must provide deterministic inspection of diagnosis history and the selected disposition. Close/reopen reconstruction must preserve every diagnosis, attribution, cause, outcome certainty, retry determination, disposition, changed-condition reference, policy/version, timestamp, and Event relationship exactly. Malformed persisted diagnosis state must produce explicit corruption diagnostics rather than a guessed result.

When diagnosis participates in a Task lifecycle transition or retry authorization, the diagnosis, disposition, changed-condition evidence when required, Task update, and corresponding Events must commit atomically. Failure of any participating write rolls back the complete operation. Diagnosis that does not transition a Task still commits its immutable record and Event atomically.

## Q7. Existing Invariants

Phase 1K independent supervision remains authoritative. Diagnosis or failure of one Task must not terminate, block, or bypass supervision of unrelated admitted Tasks.

Diagnosis does not automatically mutate provider qualification, provider health, Node health, Node administrative state, offering locations, workstation evidence or policy, scheduling priority, resource decisions, or leases. Existing lease-release ordering remains unchanged unless a concrete correctness defect is separately justified and governed.

Architecture 1 remains the normal Electron startup authority. Phase 1L introduces no startup, background, UI, or Electron integration.

## Q8. Acceptance Requirements

Controlled implementation must verify that each diagnosed Failure has one immutable, attributable, versioned diagnosis; equivalent persisted evidence produces deterministic results across restart; cause, outcome certainty, retryability, and disposition remain distinct; exactly one disposition is selected; same-path retry occurs only under existing governed retry conditions and remaining Attempt limits; non-transient retry requires relevant factual changed-condition evidence and separately authorized recovery behavior; indeterminate external outcomes require reconciliation and never authorize replay or alternative execution; verification retry remains opt-in; approval cannot be bypassed; missing or malformed evidence fails closed; immutable diagnosis history survives real SQLite close/reopen exactly; concurrent unrelated Tasks remain independently supervised; diagnosis causes no implicit provider, Node, workstation, scheduling, or lease mutation; and all prior Architecture 2 behavior remains compatible.

Implementation acceptance also requires all existing regressions, focused Phase 1L tests, TypeScript validation, the complete automated test suite, production build, real file-backed SQLite migration and reconstruction verification, Electron startup regression, diff hygiene, and engineering-log and living-document updates. Architecture 1 must remain the normal Electron startup authority.

## Q9. Deferred Boundaries

Phase 1L does not authorize automatic provider failover, automatic alternate-Node retry, circuit breakers, half-open probes, provider-specific reconciliation execution, cancellation or cancellation propagation, forced interruption, process termination, preemption, checkpointing, resume, execution migration, Node-loss recovery, dynamic replanning, graph mutation, governed web research, capability discovery or installation, generalized policy-engine infrastructure, new general-purpose tools, purpose-specific memory, UI work, Electron Architecture 2 authority cutover, distributed locking, distributed consensus, remote workers, multiple active Orchestrators, or LLM-authoritative diagnosis.

Phase 1K prohibitions against failover, alternate-Node retry, cancellation, and distributed execution remain intact. The recommendation dispositions defined by Phase 1L are durable judgments only and do not authorize their named advanced behaviors.
