# Addendum 005 — Architecture 2 Foundation

**Status:** Proposed for Product Owner and Architect approval

**Date:** 2026-08-12

**Architecture:** G.R.A.C.I. Architecture 2

**Scope:** Authoritative design specification; implementation is not authorized by this document

This addendum extends the Autonomous Personal AI Assistant Master System Specification and Addendums 001 through 004.

Where this addendum is more specific than an earlier requirement, this addendum governs. It does not modify or replace the immutable baseline. Transient deployment facts, including hostnames, addresses, ports, installed model tags, and credentials, remain configuration rather than governance.

---

## E1. Purpose and Scope

Architecture 2 defines the durable foundation on which G.R.A.C.I. can evolve from a desktop shell and collection of registries into a predominantly local/on-prem autonomous goal-execution system.

The architecture must support this closed loop:

```text
Human goal
  -> planning and task graph
  -> policy and capability resolution
  -> orchestration and scheduling
  -> execution through providers
  -> evidence collection and verification
  -> success
     or diagnosis -> bounded retry / alternative / research -> verification
```

Persistent state, approvals, safety policy, memory, observability, provenance, and recovery surround every stage. A goal, task, attempt, or consequential action must never depend solely on an LLM context window.

This document defines:

- architectural boundaries and responsibilities;
- canonical domain concepts and lifecycle semantics;
- provider-independent capability contracts;
- persistence, recovery, audit, and observability requirements;
- safety and approval behavior;
- an incremental implementation roadmap.

This document does not authorize implementation, migration, dependency changes, configuration changes, deployment, or replacement of the current application.

## E2. Architectural Principles

1. **Durable before autonomous.** Work must be reconstructable before it may run unattended.
2. **Evidence before completion.** Completion is a verified state transition, not an agent assertion.
3. **Capabilities before products.** Planning requests abstract capabilities; adapters select products and providers.
4. **Policy before side effect.** Authorization is evaluated immediately before a consequential action, not only during planning.
5. **Explicit state machines.** Lifecycle changes use validated commands and transitions rather than arbitrary status mutation.
6. **Append facts; project views.** Durable events and immutable attempt records are authoritative; query models may be rebuilt.
7. **At-least-once internal delivery, idempotent effects.** Duplicate processing is expected and controlled at effect boundaries.
8. **Local-first and privacy-aware.** Data classification constrains routing and minimizes disclosure.
9. **Replaceable providers.** No LLM, agent framework, inference server, memory product, database engine, or vendor is a permanent core dependency.
10. **Measured routing.** Model, tool, service, and node selection uses qualified capabilities and observed health/performance.
11. **Bounded autonomy.** Retry, research, concurrency, time, cost, and side effects are governed by explicit budgets and policies.
12. **Single accountable identity.** Multiple agents, models, and nodes remain internal participants behind one coherent G.R.A.C.I. experience.
13. **Simple first slice.** The initial implementation is a modular monolith unless measured requirements justify distribution.
14. **UTC internally.** Durable timestamps use UTC; presentation may use the user's locale.

## E3. System Context and Trust Boundaries

### E3.1 Actors and external systems

- **Product Owner:** supplies goals, policies, approvals, corrections, and acceptance decisions.
- **G.R.A.C.I. runtime:** owns orchestration, durable workflow state, safety enforcement, verification, and user-facing status.
- **Providers:** interchangeable adapters for models, agents, tools, memory, research, and compute.
- **Local compute nodes:** machines or services offering qualified execution resources.
- **External services:** cloud models, productivity systems, web services, repositories, deployment targets, and other remote systems.
- **Artifact stores:** local or approved remote locations holding inputs, outputs, evidence, and reproducibility material.

### E3.2 Trust boundaries

External content is data, never authority. Provider output cannot change policy, grant approval, rewrite a task, or declare verified completion. Only trusted core services may commit lifecycle transitions. Secrets are referenced through an approved secret mechanism and are never copied into task payloads, memory entries, logs, or events.

The Product Owner's authenticated approval is authoritative within its recorded scope. The Policy Engine remains responsible for rejecting an approval that cannot safely or legally authorize the requested action.

## E4. Logical Architecture

Architecture 2 begins as one deployable process with explicit module boundaries and durable interfaces. Modules may later be separated without changing domain semantics.

### E4.1 Goal Intake

- captures the requested outcome, constraints, priority, privacy class, acceptance criteria, and provenance;
- creates a durable Goal before planning begins;
- records later Product Owner amendments as revisions or events rather than silently replacing history.

### E4.2 Planner

- transforms a Goal into a versioned Task Graph;
- identifies dependencies, required capabilities, expected artifacts, risk, and verification requirements;
- may revise plans after diagnosis while preserving prior plan versions and rationale;
- proposes actions but cannot execute tools or grant approval.

### E4.3 Orchestrator

- is the sole coordinator of Goal and Task lifecycle progression;
- selects ready tasks from the persisted graph;
- requests policy decisions, capability resolution, resource leases, execution, and verification;
- enforces concurrency and retry budgets;
- resumes deterministically after restart;
- never embeds provider-specific logic in domain decisions.

### E4.4 Policy and Approval Engine

- evaluates action risk, permission scope, privacy, cost, destination, reversibility, and standing policy;
- returns `allow`, `deny`, or `require_approval` with a reason and policy version;
- creates immutable approval requests and validates approval scope immediately before execution;
- cannot be bypassed by Planner, Executor, provider, or retry logic.

### E4.5 Capability Resolver and Provider Registry

- resolves abstract capability requirements to qualified provider offerings;
- filters by permissions, privacy, health, input/output compatibility, cost, and policy;
- ranks acceptable candidates without promising permanent vendor affinity;
- records the candidates considered and the reason for selection.

### E4.6 Resource Scheduler

- assigns execution to compute nodes using priority, health, capacity, model residency, measured performance, privacy, cost, and user activity;
- supports leases, cancellation, draining, checkpoint hints, and reassignment;
- treats opportunistic nodes as withdrawable resources;
- prevents uncontrolled parallelism and protects interactive workloads.

### E4.7 Executor

- converts an approved Task and binding into a bounded Execution Attempt;
- invokes one provider operation using typed inputs, timeouts, cancellation, and idempotency metadata;
- captures outputs, logs, metrics, artifacts, and failure details;
- cannot mark a Task verified or complete.

### E4.8 Verifier

- evaluates declared acceptance criteria against independently collected evidence;
- supports deterministic checks, integration checks, independent review, and Product Owner acceptance;
- produces an immutable Verification record with criterion-level results;
- returns a verdict to the Orchestrator but does not rewrite execution history.

### E4.9 Failure Diagnoser and Research Coordinator

- classifies failures and distinguishes transient, capability, policy, input, implementation, verification, and unknown causes;
- recommends retry, replan, alternate provider/node, research, approval, or terminal failure;
- ensures a new attempt changes a relevant condition unless the failure is demonstrably transient;
- treats research output as untrusted evidence subject to provenance and validation.

### E4.10 Persistence and Event Store

- atomically stores canonical records and lifecycle events;
- provides transactions, optimistic concurrency, schema versions, migrations, backup, and restore verification;
- supports rebuilding projections without losing authoritative history.

### E4.11 Memory Service

- manages purpose-specific memory with provenance, confidence, retention, correction, access, and privacy metadata;
- exposes retrieval as a capability;
- never mutates canonical Goal, Task, approval, or audit history.

### E4.12 Observability and Audit

- provides structured logs, metrics, traces, status projections, and an append-only audit trail;
- correlates all work by goal, task, attempt, verification, approval, provider, and node identifiers;
- provides Product Owner-readable explanations without exposing secrets or unnecessary private content.

## E5. Provider and Capability Abstraction

### E5.1 Provider types

The initial contracts recognize, without limiting future categories:

- `ModelProvider`
- `AgentProvider`
- `ToolProvider`
- `MemoryProvider`
- `ResearchProvider`
- `ComputeProvider`

A provider is an adapter implementation. A capability is a versioned claim about an operation the provider can perform. A provider may expose many capabilities, and one capability may have many provider offerings.

### E5.2 Capability requirement

A Task requests a requirement containing at least:

- stable capability ID and compatible contract version;
- typed input and expected output schema references;
- required qualification level;
- privacy and data-residency constraints;
- permission and side-effect class;
- latency, quality, cost, and resource constraints where relevant;
- required features such as vision, tool use, context capacity, or checkpointing.

### E5.3 Provider offering

An offering records at least:

- provider and adapter identity/version;
- capability ID and contract version;
- configuration reference, not embedded secrets;
- health and last successful check;
- qualification evidence and expiry/requalification trigger;
- limitations, permissions, supported formats, and side effects;
- privacy destination, cost model, expected latency, and measured reliability;
- eligible compute/node classes.

### E5.4 Invocation contract

Every invocation uses a versioned request envelope containing correlation IDs, deadline, cancellation token, idempotency key where applicable, input artifact references, privacy classification, and policy decision reference. The response distinguishes:

- successful typed output;
- rejected request;
- retryable provider failure;
- non-retryable provider failure;
- indeterminate outcome, especially for external side effects.

Provider output is stored as an Attempt result. It is not direct authority to mutate Task or Goal state.

## E6. Canonical Domain Model

All durable entities use stable opaque identifiers, schema versions, creation/update timestamps, revision or concurrency tokens, and provenance. Large payloads are referenced as artifacts rather than duplicated into records.

### E6.1 Goal

A Goal represents the Product Owner's desired outcome.

Required concepts:

- objective and constraints;
- priority and privacy classification;
- acceptance criteria;
- status and terminal reason;
- active plan version;
- origin and Product Owner amendments;
- aggregate progress derived from Tasks;
- created, updated, and completed timestamps.

Goal states are `draft`, `planning`, `active`, `waiting_for_approval`, `blocked`, `verifying`, `succeeded`, `failed`, and `cancelled`.

### E6.2 Task

A Task is the smallest durable schedulable unit that can be attempted and verified independently.

Required concepts:

- parent Goal and plan version;
- title, objective, and typed input references;
- dependency edges and dependency policy;
- required capabilities and routing constraints;
- risk, privacy, priority, deadline, and budgets;
- acceptance criteria and verification plan;
- retry policy;
- status, terminal reason, and selected output artifacts;
- optional parent Task for decomposition, without using nesting as a substitute for dependency edges.

### E6.3 Task dependency

Dependency edges are explicit and validated as an acyclic graph for executable plans. An edge records predecessor, successor, condition (`success`, `completion`, or explicit predicate), and provenance. A task becomes ready only when all required dependency conditions are satisfied.

### E6.4 Execution Attempt

An Attempt is an immutable record of one bounded execution of one Task. It records:

- attempt number and triggering decision;
- provider offering, model/agent/tool version, and compute node;
- input artifact versions and parameters;
- policy and approval references;
- start/end timestamps, deadline, and resource/cost metrics;
- outcome and structured failure;
- output artifacts, logs, and checkpoints;
- idempotency key and external-operation reconciliation status.

Corrections create another Attempt; they do not overwrite a previous Attempt.

### E6.5 Verification and evidence

A Verification binds a Task, Attempt or artifact set, verification-plan version, verifier identity, criterion results, evidence references, and verdict. Evidence records type, source, collection method, timestamp, integrity metadata where practical, and provenance.

Verdicts are `passed`, `failed`, `inconclusive`, and `requires_human_acceptance`.

### E6.6 Failure

A Failure record includes category, stable code, summary, sanitized detail, retryability, suspected cause, affected capability/provider/node, evidence, and recommended disposition. Initial categories are:

- `transient_infrastructure`
- `resource_unavailable`
- `provider_or_capability_mismatch`
- `invalid_input_or_precondition`
- `policy_or_approval`
- `execution_defect`
- `verification_failure`
- `external_outcome_indeterminate`
- `cancelled_or_preempted`
- `unknown`

### E6.7 Approval

An Approval Request records the exact proposed action, parameters or digest, target, side-effect/risk class, expected cost, data disclosure, requested scope, expiry, policy version, and requesting Task/Attempt. An Approval Decision records actor, decision, scope, conditions, timestamp, and optional expiry.

Approval is not reusable outside its recorded scope. Material changes to action, destination, disclosure, cost, or consequence invalidate prior approval.

### E6.8 Artifact

An Artifact records a logical identity, immutable version, content-address or integrity digest where practical, media type, storage reference, producer Attempt, source inputs, privacy class, retention policy, verification state, and supersession relation.

### E6.9 Event

Every material lifecycle change emits a durable event containing event ID, aggregate ID/type, sequence number, event type/version, actor, correlation/causation IDs, timestamp, sanitized payload, and policy/provenance references where relevant.

## E7. Task State Machine

The canonical Task states are:

- `planned`: valid Task exists in an approved or active plan version;
- `blocked`: dependencies or required preconditions are not satisfied;
- `ready`: dependencies are satisfied and the Task may be considered for scheduling;
- `waiting_for_approval`: a scoped approval is required;
- `scheduled`: provider and resource bindings have been selected and leased;
- `running`: an Attempt is active;
- `verifying`: execution output exists and acceptance is being evaluated;
- `retry_pending`: a retry or alternative Attempt is authorized but not yet ready;
- `succeeded`: all required criteria passed or authorized Product Owner acceptance was recorded;
- `failed`: no allowed recovery remains or a terminal failure decision was made;
- `cancelled`: cancellation was accepted and reconciliation completed;
- `superseded`: a newer plan version intentionally replaced the Task.

Permitted normal transitions are:

```text
planned -> blocked | ready | cancelled | superseded
blocked -> ready | waiting_for_approval | failed | cancelled | superseded
ready -> waiting_for_approval | scheduled | failed | cancelled | superseded
waiting_for_approval -> ready | failed | cancelled | superseded
scheduled -> running | retry_pending | failed | cancelled
running -> verifying | retry_pending | failed | cancelled
verifying -> succeeded | retry_pending | waiting_for_approval | failed | cancelled
retry_pending -> blocked | ready | waiting_for_approval | failed | cancelled | superseded
```

Terminal states are `succeeded`, `failed`, `cancelled`, and `superseded`. Administrative repair of corrupted state is a separately authorized recovery operation and must emit an audit event; it is not an ordinary transition.

Transition guards include:

- only the Orchestrator may request a lifecycle transition;
- Persistence validates expected revision and transition legality atomically;
- `scheduled` requires a valid provider binding and resource lease;
- `running` requires a persisted Attempt before invocation;
- `verifying` requires durable result/evidence references or a recorded indeterminate outcome;
- `succeeded` requires a passing Verification for every required criterion;
- a denied or expired approval cannot lead to execution;
- retry count, time, cost, and risk budgets must remain available;
- cancellation of an indeterminate external action cannot become terminal until reconciliation or explicit escalation.

## E8. Orchestration and Execution Lifecycle

1. Persist the Goal and its acceptance criteria.
2. Create and validate a versioned Task Graph.
3. Mark dependency-satisfied Tasks `ready`.
4. Resolve required capabilities to qualified provider candidates.
5. Evaluate policy and obtain approval when required.
6. Acquire a time-bounded resource lease and persist the selected binding.
7. Create the Attempt with its idempotency and correlation metadata.
8. Dispatch through the Executor and emit progress/heartbeat events.
9. Persist outputs, artifacts, metrics, and structured outcome.
10. Release the resource lease.
11. Run the Verification plan.
12. Transition to `succeeded`, or enter diagnosis and bounded recovery.
13. Recompute downstream readiness and Goal progress.
14. Verify Goal-level acceptance before marking the Goal `succeeded`.

The Orchestrator must use transactional outbox/inbox or an equivalent atomic delivery pattern when durable state changes cause asynchronous work. Internal messages may be delivered at least once; handlers must be idempotent.

## E9. Verification Lifecycle

Verification is designed before execution whenever practical.

Each acceptance criterion defines:

- a stable criterion ID;
- expected condition and severity;
- evidence source and collection method;
- verifier type and independence requirement;
- timeout and inconclusive behavior.

Verification order favors authoritative and deterministic evidence:

1. schema and invariant validation;
2. direct inspection of produced state or artifacts;
3. automated unit, integration, build, runtime, health, or visual checks;
4. expected-output or contract comparison;
5. independent model/agent review where judgment is required;
6. Product Owner acceptance where the criterion is subjective or consequential.

A model review may strengthen evidence but cannot override failing executable evidence. Verification failure creates a Failure and feeds diagnosis. Verifier independence is configurable; for high-risk work, the producing provider instance must not be the sole verifier.

## E10. Failure, Retry, Alternative, and Research Lifecycle

1. Normalize errors and evidence into a Failure.
2. Classify cause, retryability, consequence, and outcome certainty.
3. Check whether any external side effect already occurred.
4. Select one disposition: reconcile, retry, use alternate provider/node, revise input, replan, research, request approval, fail, or cancel.
5. Confirm remaining attempt, elapsed-time, cost, and risk budgets.
6. Record the decision and the condition changed from the previous Attempt.
7. Apply bounded backoff and jitter for transient failures.
8. Execute a new Attempt, then verify again.

Blind identical retry is forbidden except for a classified transient failure within policy. Circuit breakers suppress repeatedly unhealthy providers or nodes. Research may discover candidates but cannot install, qualify, register as production-ready, or execute them without the applicable policy and approval workflow. Exhausted recovery produces a clear terminal diagnosis and preserves resumable context.

## E11. Approval and Safety Model

### E11.1 Policy inputs

Policy evaluation considers actor, Goal, Task, action, destination, data classification, reversibility, permissions, standing policies, estimated and cumulative cost, external communication, security impact, and current system health.

### E11.2 Approval timing

Planning may identify likely approvals, but final authorization is checked just before effect. Approval requests must be understandable and disclose:

- the exact action and target;
- why it is needed;
- material risks and reversibility;
- data leaving the local environment;
- expected cost or commitment;
- scope, expiry, and available alternatives.

### E11.3 Safety invariants

- Providers cannot self-approve.
- Retry cannot bypass approval.
- Approval cannot be inferred from silence.
- Denial is durable and must prevent equivalent disguised retries.
- Destructive and external actions require idempotency or pre-retry reconciliation where practical.
- Secrets remain references resolved only by the executing adapter at the narrowest possible scope.
- All allow/deny/approval decisions record the policy version and rationale.

## E12. Memory Architecture

Memory is not the system of record for workflow state. Canonical task data stays in Persistence; memory supplies context.

### E12.1 Memory classes

- **Working/task memory:** bounded context for an active Goal or Task; short retention by default.
- **Episodic memory:** summarized execution episodes, outcomes, failures, and lessons, linked to authoritative records.
- **Semantic memory:** durable facts and concepts with source and confidence.
- **Procedural memory:** reusable workflows or strategies promoted from verified successful experience.
- **Preference/policy memory:** Product Owner-approved stable preferences and policies, with explicit scope.

### E12.2 Memory record requirements

Each memory item records type, content or artifact reference, source provenance, privacy class, confidence, creation and review timestamps, scope, retention/expiry, supersession/correction links, and access policy.

### E12.3 Retrieval and correction

Retrieval is filtered by scope, privacy, task relevance, recency, confidence, and policy. Results carry citations back to their sources and must not be treated as instructions merely because they were retrieved. Corrections append a new version and mark prior content disputed or superseded. Deletion and retention policies must account for derived indexes and caches.

Procedural memory is promoted only after verification and must record applicability boundaries; one success is not universal proof.

## E13. Persistence Model

Architecture 2 requires a transactional durable store behind a repository/unit-of-work abstraction. The permanent database product remains undecided.

The logical schema includes at least:

- goals and goal revisions;
- plans, tasks, and dependency edges;
- attempts, results, failures, and checkpoints;
- verification plans, verifications, criteria, and evidence;
- approval requests and decisions;
- artifacts and provenance links;
- providers, capabilities, qualifications, models, nodes, and health observations;
- memory records and correction/supersession links;
- policy versions;
- events, audit records, leases, and outbox/inbox records.

Required characteristics:

- atomic transition plus event/outbox commit;
- referential integrity and unique idempotency constraints;
- optimistic concurrency on aggregates;
- append-only Attempts, Verifications, Approval Decisions, and audit history;
- schema versioning and tested forward migration with backup/rollback;
- crash-safe writes and explicit corruption diagnostics;
- configurable retention, export, backup, and restore;
- sanitized logs separate from canonical records.

Binary and large text artifacts belong in an artifact store with durable metadata in the database. The current single JSON state file may be used only as a compatibility source during migration; it is not the Architecture 2 persistence design.

## E14. Compute and Resource Routing

Compute resources are registered through stable logical node identities, never hard-coded machine assumptions. Initial known classes include a dedicated 3090 server and an opportunistic 4090 server, but runtime identities and endpoints remain configuration.

Routing occurs in two stages:

1. choose a qualified capability/provider/model compatible with the Task;
2. choose an eligible healthy node/resource instance for that offering.

Selection considers quality threshold, qualification freshness, privacy, permissions, node health, GPU/VRAM/RAM/CPU, model residency, queue depth, latency, measured throughput, task priority, deadline, cost, and user activity.

The 4090-class workstation must support an availability policy that drains or excludes it while gaming activity is present, including when Mod Organizer 2 is running. Detection is adapter/configuration behavior, not a hard-coded core dependency.

Resource leases have expiry and heartbeat. On drain or failure, the scheduler stops new assignments, requests checkpoint/cancellation where supported, records the interruption, and safely resumes or reroutes. Non-checkpointable consequential operations require outcome reconciliation before reassignment.

## E15. Observability and Audit

The system must answer, for any active or historical Goal:

- what is happening and why;
- current Goal/Task states and blockers;
- chosen provider, model/tool, and node;
- policy and approval status;
- attempts, failures, retries, and alternatives;
- resource and cost consumption;
- artifacts and their provenance;
- verification evidence supporting completion.

### E15.1 Telemetry

- **Structured logs:** diagnostic events with correlation IDs and redaction.
- **Metrics:** queue depth, state durations, success/failure rates, retries, provider/node health, latency, throughput, resource use, and cost.
- **Traces:** causal spans from Goal intake through provider calls and verification.
- **Status projections:** human-readable current state rebuilt from durable records.

### E15.2 Audit requirements

The audit stream is append-only, ordered per aggregate, timestamped, attributable, versioned, and protected from secret leakage. It records lifecycle transitions, plan revisions, routing decisions, policy evaluations, approval decisions, provider invocations, artifact production, verification verdicts, recovery actions, and administrative repair.

Telemetry failure should degrade visibility but must not corrupt workflow state or crash core execution. Loss of mandatory audit durability must fail closed for consequential actions.

## E16. Restart and Recovery Behavior

At startup G.R.A.C.I. must:

1. validate configuration and schema compatibility;
2. establish storage health and acquire the runtime identity/leadership guard appropriate to the deployment;
3. load policy and provider/capability metadata;
4. reconcile expired leases and incomplete outbox/inbox delivery;
5. inspect Tasks in `scheduled`, `running`, `verifying`, and `retry_pending`;
6. query providers or external systems where an outcome is indeterminate;
7. resume safe work, schedule a fresh Attempt, wait for approval, or mark a diagnosed failure;
8. refresh node/provider health and rebuild status projections;
9. expose degraded/failed/unknown health without hiding recovery actions.

G.R.A.C.I. must never blindly repeat an external side effect after restart. Checkpoints are versioned artifacts tied to the exact Attempt and provider capability; unsupported migration falls back to a new Attempt only when safe.

Recovery operations record the detected condition, decision, action, restored state, and verification result. Known-good status requires successful tests and runtime/health verification as governed by Addendum 003.

## E17. Incremental Implementation Roadmap

### Slice 1 — Durable workflow kernel

- canonical Goal, Task, dependency, Attempt, Verification, Failure, Approval, Artifact, and Event types;
- transactional persistence abstraction and one local implementation;
- validated Task state machine with optimistic concurrency;
- minimal Orchestrator for a pre-authored DAG;
- one in-process test provider;
- deterministic verification;
- bounded retry and approval pause/resume;
- restart recovery and audit/status queries;
- migration/import strategy for existing JSON state, without silently treating it as authoritative.

### Slice 2 — Capability and provider resolution

- versioned provider contracts and capability registry;
- qualification/health metadata;
- policy-filtered resolver and routing explanation;
- adapt existing Ollama support behind a Model Provider boundary.

### Slice 3 — Multi-node scheduling

- node discovery adapters, leases, health observations, draining, priority, cancellation, and failover;
- workload protection and opportunistic 4090 availability policy;
- measured performance inputs.

### Slice 4 — Failure intelligence and research

- normalized failure taxonomy, circuit breakers, alternative selection, replanning, and governed research for missing capabilities.

### Slice 5 — Purpose-specific memory

- memory provider interface, provenance-aware retrieval, correction, retention, and verified procedural promotion.

### Slice 6 — Product observability and expanded autonomy

- Product Owner task graph/status views, evidence inspection, cost/resource reporting, advanced policies, and broader qualified providers.

Each slice must satisfy Addendum 001 runtime verification and Addendum 003 recovery requirements before the next slice depends on it.

## E18. First-Implementation Non-Goals

The first Architecture 2 implementation must not attempt:

- unrestricted autonomous planning or self-modification;
- a distributed microservice deployment;
- automatic installation or adoption of discovered tools/models;
- permanent selection of a database, workflow engine, vector database, or agent framework without qualification;
- generalized semantic memory or autonomous preference inference;
- arbitrary cross-machine task migration when providers do not support checkpoints;
- exactly-once distributed execution as a blanket guarantee;
- autonomous consequential external communication, purchasing, deployment, or destructive action;
- a complete plugin marketplace or every provider category;
- optimization before correctness, durability, auditability, and recovery are demonstrated;
- replacement of the UI beyond the minimum needed to observe and approve the first slice.

## E19. Relationship to the Existing Repository

The current Electron/TypeScript application is a useful shell and compatibility surface, not an Architecture 2 contract.

- `src/core/tasks/manager.ts` has four mutable in-memory states and no dependencies, attempts, verification, approvals, retry policy, persistence integration, or transition guards. It must not be extended ad hoc into the canonical engine.
- `src/core/state/store.ts` uses a process-local cache and whole-file JSON writes without transactions, concurrency control, schema migration, or crash recovery. It is insufficient for Architecture 2 authoritative state.
- existing Tool, Capability, Model, and Node registries are minimal maps. Their names may remain, but their persisted schemas and responsibilities require redesign behind versioned interfaces.
- current configuration includes transient endpoint/model defaults. Architecture 2 requires these to remain editable deployment configuration and not architectural constants.
- existing Ollama services should become adapter implementations behind provider/capability boundaries rather than dependencies of the Orchestrator.
- Electron may remain the initial host and UI, while the domain kernel must remain independent of Electron APIs.

Implementation must preserve useful behavior through explicit adapters or migration. Existing experimental types must not silently define the new schema.

## E20. Assumptions

1. A single-user, local-first deployment is the initial operating environment.
2. One authoritative G.R.A.C.I. runtime coordinates workflow state in the first implementation, while multiple remote compute providers may participate.
3. The initial durable store can run locally and provide real transactions and integrity constraints.
4. Providers may be unreliable, duplicate responses, time out after completing work, or disappear mid-attempt.
5. Product Owner approvals can initially occur through the desktop application and be durably authenticated to the local user/session.
6. Artifact content may outgrow the primary database and therefore uses referenced storage.
7. Privacy classification is assigned at intake and may be raised, never silently lowered, by derived work.
8. Existing repository code may be adapted or replaced during a later authorized implementation phase.

## E21. Unresolved Decisions Requiring Approval

The following are intentionally unresolved and must be decided during or before their implementation slice:

1. **Primary persistence engine:** embedded SQLite-family store versus a server database; select through transaction, migration, concurrency, backup, and operational qualification.
2. **Event model depth:** state plus append-only domain events versus full event sourcing. This specification requires durable events but does not require full event sourcing.
3. **Workflow leadership:** single-process lock versus lease-based coordinator for future active/passive runtime operation.
4. **Artifact store:** filesystem content-addressed storage initially versus database blobs or an object-store adapter.
5. **Policy representation:** typed code/config rules initially versus a dedicated policy engine later.
6. **Approval authentication and standing-policy UX:** exact local identity, expiry, delegation, and revocation mechanics.
7. **Task graph revision semantics:** replacement of unstarted subgraphs versus finer-grained plan branching/merging.
8. **Goal success aggregation:** whether all required Tasks must pass or whether Goal-level acceptance may supersede selected Task failures, with an explicit waiver record.
9. **Memory retention defaults:** retention periods, deletion semantics, and when procedural memories become eligible for promotion.
10. **Audit tamper evidence:** ordinary append-only database controls initially versus hash chaining/signing for higher-assurance deployments.
11. **HA and remote control boundary:** whether and when a second orchestrator, web API, or remote UI is in scope.
12. **Cloud routing defaults:** which privacy classes, if any, may use approved cloud providers without per-task approval.

## E22. Architecture 2 Acceptance Criteria

This design is ready for implementation planning only after Product Owner and Architect review confirms that:

- the domain model and state machine represent the required autonomy loop;
- verification is authoritative over provider self-report;
- approvals cannot be bypassed through retry or recovery;
- provider and compute abstractions avoid permanent vendor/node coupling;
- persistence and recovery prevent loss or unsafe duplicate effects;
- memory is separated from canonical workflow state;
- the incremental roadmap begins with the smallest durable, testable slice;
- unresolved decisions are explicitly accepted, resolved, or assigned to an implementation slice.

Until that review occurs, this addendum is a proposed governance document and Architecture 2 implementation remains paused.
