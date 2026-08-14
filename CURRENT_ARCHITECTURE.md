# G.R.A.C.I. Current Architecture

> **Living document:** Update this file whenever Architecture 2 module boundaries, lifecycle behavior, persistence authority, runtime composition, or intentionally deferred capabilities change. This is an implementation map, not immutable governance. The master specification and numbered addenda under `docs/governance/` remain authoritative.

**Architecture represented:** Implemented and accepted through Architecture 2 Phase 1K

**Repository HEAD:** `522f50f725f2038943d548a3cb3e41e02effa062`

## System Shape

### Simple Explanation

G.R.A.C.I. is being built like a robot with replaceable parts. One part keeps the job list, one decides what may run, one reserves machines, one performs work, one checks the result, and one records everything. These parts currently live in one program so they are easier to operate and test, but their responsibilities are separated.

### Technical Detail

Architecture 2 is a TypeScript modular monolith under `src/architecture2/` with these primary boundaries:

- `domain/`: canonical records and branded identifiers.
- `persistence/`: provider-independent contract and SQLite implementation.
- `workflow/`: state machine, dependency evaluation, graph validation, deterministic scheduling, orchestration, and queue inspection.
- `execution/`: provider-neutral Task execution contract and deterministic test provider.
- `verification/`: independent Task verification contract and deterministic verifier.
- `providers/`: capability/provider resolution and Ollama Model Provider adapter.
- `resources/`: Node inspection, deterministic resource scheduling, process snapshots, and workstation availability policy.
- `legacy/`: read-only Architecture 1 state assessment and inert history import.
- `runtime/`: explicit caller-configured Architecture 2 composition.

One authoritative process is assumed. No distributed consensus or worker service exists.

## Task and Workflow Model

### Simple Explanation

A Goal is the destination, such as "prepare a report." Tasks are the individual jobs needed to get there. Each Task moves through a controlled checklist instead of anyone freely scribbling "done" beside it.

### Technical Detail

Canonical records include Goal, Goal criterion, immutable Task Graph Revision, Task, Task dependency, Attempt, Verification, Failure, Approval, Artifact metadata, and Event. The Task is the smallest durable schedulable unit.

The implemented Task lifecycle uses:

```text
planned -> blocked | ready
ready -> scheduled
scheduled -> running
running -> verifying | retry_pending | waiting_for_approval | failed
verifying -> succeeded | retry_pending | waiting_for_approval | failed
retry_pending -> blocked | ready | failed
waiting_for_approval -> ready | failed
```

Cancellation and supersession exist in the domain state vocabulary, but Phase 1K does not implement user cancellation or cancellation propagation. `TaskStateMachine` centrally validates transition legality and evidence guards. Persistence independently enforces optimistic Task versions and atomic writes.

## Persistence and SQLite Authority

### Simple Explanation

SQLite is G.R.A.C.I.'s notebook. The assistant does not rely on remembering what happened in a conversation. Important jobs, attempts, decisions, reservations, and results are written into the notebook before later steps trust them.

### Technical Detail

`SqliteArchitecture2Persistence` is the current authoritative store behind `Architecture2Persistence`. Callers supply the database path. The implementation uses built-in `node:sqlite`, foreign keys, strict tables, WAL mode, `synchronous = FULL`, a busy timeout, and `BEGIN IMMEDIATE` write transactions.

Current schema version is 8. Phase 1K required no migration because existing Task, Attempt, decision, lease, and Event records can represent multiple running Tasks.

Important invariants include:

- State changes and corresponding Events commit atomically.
- Goal and Task updates use optimistic versions.
- Attempts are unique per `(task_id, attempt_number)`.
- Terminal Attempts and historical evidence are immutable.
- Task graph revisions and dependencies are immutable.
- Events are append-only, globally sequenced, and SHA-256 hash chained.
- Resource capacity is rechecked within the lease-acquisition transaction.
- Resource-aware workflow scheduling atomically writes the Task transition, scheduling decision, lease, and Events.

## Dependency Handling

### Simple Explanation

Dependencies are rules like "put your shoes on before going outside." A later Task cannot start merely because it is convenient; its required earlier Tasks must reach the right outcome first.

### Technical Detail

Complete Task graphs are admitted transactionally after deterministic validation. Kahn topological processing rejects cycles. Dependency edges support:

- `success`: predecessor must be `succeeded`.
- `completion`: predecessor may be any canonical terminal state.
- `predicate`: remains waiting because predicate evaluation is deferred.

A failed, cancelled, superseded, or transitively failure-blocked predecessor blocks a required success-dependent successor with `required_dependency_failed`. Missing persisted predecessors are treated as corruption, not ordinary waiting.

## Queue and Scheduling

### Simple Explanation

The scheduler is a traffic controller. It looks at jobs that are truly ready and admits them in a stable line: oldest recorded job first, with the job ID breaking ties. It does not invent a second hidden line.

### Technical Detail

Persisted canonical Tasks and lifecycle states are the queue. There is no queue table, broker, or authoritative in-memory queue.

Only `ready` Tasks are schedulable. `getReadyTasksInScheduleOrder()` orders them by:

1. Persisted `createdAt` ascending.
2. Task ID lexical ascending.

Priority does not currently change this ordering. Queue inspection is a deterministic read-only projection of canonical state, dependencies, blockers, Attempt count, and latest Failure.

## Bounded Concurrent Scheduling

### Simple Explanation

The traffic controller may now let two independent workers work at the same time, but only if the configured number of work spaces allows it. Jobs that depend on each other still wait. The default remains one worker, so concurrency must be chosen deliberately.

### Technical Detail

Phase 1K adds `maxConcurrentTasks` to `OrchestratorOptions`. It must be a positive integer and defaults to `1`. The Orchestrator admits ordered ready Tasks until the configured slot limit is reached and independently supervises their settled results.

Properties:

- Admission order remains deterministic; completion order may reflect runtime timing.
- One Task's execution/verification failure or approval pause does not terminate unrelated admitted work.
- Fail-fast aggregate promise behavior is not used.
- One Orchestrator instance rejects overlapping `run()` invocations.
- Runtime slot accounting is process-local; canonical Task and Attempt state is durable.
- If an internal supervision error occurs, already admitted work remains supervised before the run reports the error.

This is bounded concurrency inside one process, not distributed orchestration.

## Attempts and Retries

### Simple Explanation

Every try is written on a new page. G.R.A.C.I. never erases a failed try and pretends the next try was the first. Temporary problems may be tried again, but only a limited number of times and only under explicit rules.

### Technical Detail

Each invocation creates an immutable Attempt identity with a per-Task attempt number, provider offering, optional compute Node, input snapshot, timestamps, and structured result. Attempt history determines the durable retry budget across restart.

The default maximum is three total Attempts unless a valid Task retry policy overrides it. Automatic retry behavior is:

- `transient`: retryable while budget remains.
- `verification_failed`: retryable only when `retryVerificationFailures` is true.
- `permanent`, `approval_required`, and `external_outcome_indeterminate`: not automatically retried.

Before `retry_pending -> ready`, the Orchestrator revalidates the latest relevant Failure, retryability, classification, and remaining budget. Unprovable authorization fails closed.

## Execution and Verification

### Simple Explanation

The worker who says "I finished" is not the final judge. A separate checker examines the evidence before G.R.A.C.I. marks the Task successful.

### Technical Detail

`TaskExecutionProvider` accepts a provider-neutral request and returns structured success or failure. Provider exceptions are normalized into Task execution failure. A successful Attempt transitions the Task to `verifying`, not `succeeded`.

`TaskVerifier` independently evaluates execution evidence. A passing Verification is required for `verifying -> succeeded`. A rejecting Verification records durable evidence and either enters an explicitly allowed retry or fails the Task. The deterministic provider and verifier supplied in the repository are test components.

## Approvals

### Simple Explanation

If a job reaches a step that needs permission, G.R.A.C.I. parks that one job and writes down exactly what permission is needed. Other unrelated workers may continue. Silence is never treated as approval.

### Technical Detail

An `approval_required` execution result atomically completes the Attempt as failed, records the Failure and scoped Approval request, and transitions the Task to `waiting_for_approval`. Explicit approval records the durable decision before returning the Task to `ready`; denial records its reason and fails the Task.

Approval state survives restart. Approval cannot bypass retry or verification rules. The current API is programmatic; a Product Owner approval UI and generalized policy engine are deferred.

## Provider and Model Abstraction

### Simple Explanation

G.R.A.C.I. asks for an ability, such as generating text, rather than permanently hiring one named model. It checks a directory of providers and only chooses an entry with suitable qualifications, health, privacy, permissions, quality, and cost limits.

### Technical Detail

Architecture 2 distinguishes Providers, Capabilities, Provider Offerings, model identity, Qualifications, health observations, and durable resolution decisions. `DeterministicProviderResolver` filters and ranks offerings with stable rejection reasons and tie-breaking.

Qualification is explicit evidence; provider availability or model inventory does not imply qualification. The selected offering is recorded before invocation. Secrets and endpoint details remain caller-owned configuration references.

`OllamaModelProvider` implements a versioned boundary for health/version inspection, model inventory, and bounded non-streaming text generation. It is caller-configured and independent of Architecture 1 singleton registries. Cloud routing, streaming, multimodal generation, embeddings, tool calling, and automatic qualification are deferred.

## Nodes and Resources

### Simple Explanation

Nodes are the computers or services that can do work. Before assigning a job, G.R.A.C.I. checks whether a machine is active, healthy, suitable for the information, and large enough for the requested work.

### Technical Detail

Stable logical Nodes have caller-owned configuration references and administrative state: `active`, `draining`, or `disabled`. Provider offerings may have enabled locations on Nodes with declared integer capacity and permitted privacy classes.

`DeterministicResourceScheduler` filters by Node existence/state, location enablement, fresh healthy evidence, privacy compatibility, and capacity after active unexpired leases. Eligible candidates rank by available capacity descending, health observation recency descending, Node ID, then location ID.

Provider-offering resolution and resource/node selection are separate durable decisions. Configured-node inspection is explicit and records sanitized health and inventory evidence without creating qualifications or locations.

## Resource Leases

### Simple Explanation

A lease is like reserving a shared tool so two people do not fight over it. If a job reserves all available capacity, nobody else can use that location until the reservation is released or expires.

### Technical Detail

Resource leases bind a scheduling decision, offering, location, Node, capacity, acquisition time, expiry, and status. Acquisition transactionally rechecks active unexpired capacity under SQLite write serialization. Known execution completion or failure releases the lease while retaining history.

For resource-aware workflow admission, `scheduleTaskWithResource()` atomically commits `ready -> scheduled`, the scheduling decision, active lease, and Events. A capacity conflict returns deferred admission with no Task transition, decision, lease, Event, or Attempt.

If an ordered ready Task cannot acquire resources, it remains `ready`, consumes no retry budget, and does not prevent later ready Tasks from being considered. Full-capacity leasing supplies effective exclusivity; no distributed lock service exists.

## Workstation Availability

### Simple Explanation

If a compute machine is also the user's gaming workstation, G.R.A.C.I. can take a careful snapshot of running program names, recognize configured games or Mod Organizer 2, recommend that the machine stop receiving new work, and apply that recommendation only through a separate recorded policy action.

### Technical Detail

The Windows process adapter uses a fixed executable and fixed arguments without a shell, enforces timeout/output bounds, and persists only normalized executable basenames. Versioned exact-basename rules produce `recommend_draining`, `recommend_active`, or `inconclusive` evidence.

Evidence alone cannot mutate Node state. `WorkstationAvailabilityPolicy` requires the exact persisted evaluation, rule fingerprint, freshness bound, expected Node state/version, policy identity/version, actor, reason, and time. It records applied, rejected, and no-change decisions. Reactivation requires matching policy ownership. Draining blocks new leases but does not cancel active work.

Evaluation and application are caller-invoked. Background polling and scheduler-triggered evaluation remain deferred.

## Recovery Semantics

### Simple Explanation

After the lights go out, G.R.A.C.I. checks its notebook instead of guessing. If a worker may have performed an outside action but the result cannot be proven, G.R.A.C.I. marks the outcome uncertain and stops rather than risk performing it twice.

### Technical Detail

On each run, the Orchestrator reconstructs graph position from persisted Tasks, dependencies, Attempts, Verifications, Failures, and approvals. Terminal Tasks are not automatically re-executed. Planned and retry-pending eligibility is recomputed from durable evidence.

Persisted `running` work must have a matching running Attempt. Without provider reconciliation, interrupted running Attempts become `indeterminate`, record non-retryable `external_outcome_indeterminate` Failures, and fail atomically. Interrupted `scheduled` Tasks also fail conservatively. Corrupt running state without an Attempt produces an explicit error.

Phase 1K preserves this behavior for multiple running Tasks. Automatic replay, checkpoint resume, failover, migration, and external-effect reconciliation are deferred.

## Audit and Governance

### Simple Explanation

G.R.A.C.I. keeps both a rulebook and a flight recorder. The rulebook says what it is allowed to become; the flight recorder records important changes and workflow events so a future engineer can understand what happened.

### Technical Detail

Governance precedence is:

1. `docs/governance/MASTER_SYSTEM_SPEC.md`
2. Numbered addenda in ascending order
3. `docs/governance/GOVERNANCE_INDEX.md` for precedence and change policy

The master specification is immutable. New requirements use the next numbered addendum. `CURRENT_STATUS.md` and `CURRENT_ARCHITECTURE.md` are living summaries and cannot supersede governance.

Canonical Events are append-only, ordered, attributable, and hash chained. Engineering history is separated into `DEVELOPMENT_LOG.md`, `TEST_LOG.md`, `FAILURE_LOG.md`, and `DECISION_LOG.md`. Sensitive data and secrets must not be stored in workflow evidence or logs.

## Architecture 1 and Electron Relationship

### Simple Explanation

The desktop shell and the new engine currently sit beside each other. Starting the application opens the older shell. Engineers must deliberately construct the newer engine with a database and execution components. The switch has not been thrown yet.

### Technical Detail

`src/main.ts` is the live Electron startup path. It creates the BrowserWindow and loads the current static UI. It does not import or call `bootstrapArchitecture2`.

Architecture 2 composition requires explicit `databasePath`, `executionProvider`, and `verifier` configuration. Architecture 1 JSON state is not authoritative Architecture 2 state. Explicit legacy import preserves eligible records only as immutable, non-schedulable history and does not fabricate Goals, Attempts, Verifications, qualifications, or success.

Architecture 2 becoming the Electron authority, UI redesign, approval UX, and automatic legacy promotion require later governance and implementation.

## Intentionally Deferred Architecture

### Simple Explanation

Several advanced robot features are deliberately left disconnected until the foundation can support them safely. "Not built yet" is a boundary, not an accidental omission.

### Technical Detail

Major deferred capabilities include:

- Autonomous planning, replanning, and dynamic graph mutation.
- Predicate dependency execution.
- Generalized policy engine and standing approvals.
- User cancellation, preemption, checkpointing, and forced interruption.
- Node failover, alternate-node retry, execution migration, and reconciliation.
- Distributed locks, multiple Orchestrators, remote workers, and high availability.
- Dynamic load balancing, dynamic concurrency, speculative execution, and priority displacement.
- Automatic discovery, polling, monitoring, and scheduler-triggered workstation policy.
- Failure diagnosis, circuit breakers, governed research, and generalized alternatives.
- Purpose-specific memory and retrieval.
- Broad tool, agent, cloud, productivity, voice, media, notification, and UI integration.
- Architecture 2 Electron authority cutover and production hardening.

These boundaries are summarized here; the latest numbered addendum is authoritative for any implementation phase.
