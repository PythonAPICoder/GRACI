# G.R.A.C.I. Current Status

> **Living document:** Update this file whenever an Architecture 2 phase changes implemented behavior, verification evidence, runtime authority, major limitations, or the recommended next phase. Governance under `docs/governance/` remains authoritative when this summary differs from an approved specification.

**Generated from repository HEAD:** `522f50f725f2038943d548a3cb3e41e02effa062` (`feat: add bounded concurrent scheduling`)

**Accepted implementation through:** Architecture 2 Phase 1K, Bounded Concurrent Scheduling (`ADDENDUM_016_ARCHITECTURE_2_PHASE_1K.md`)

## Product Direction

### Simple Explanation

G.R.A.C.I. is intended to become a dependable personal AI assistant: less like a chat window and more like a robot that can understand a goal, break it into safe steps, use the right tools and AI models, check its own work, recover from problems, and explain what it did. The robot is still being assembled. Its internal workflow engine is substantially built, but most user-facing abilities have not yet been connected to the desktop application.

### Technical Detail

The governing mission is a local-first autonomous goal-execution system with durable workflows, provider-independent capabilities, multiple compute nodes, policy and approval controls, evidence-based verification, bounded recovery, auditability, and one coherent assistant identity. See `docs/governance/MASTER_SYSTEM_SPEC.md` and Addendums 001 through 005.

Architecture 2 is being developed as a modular monolith with explicit domain, persistence, workflow, execution, verification, provider, resource, and runtime-composition boundaries. It is designed to evolve without making SQLite, Ollama, Electron, one model, or one machine a permanent domain dependency.

## Completed Work

### Simple Explanation

The project has built G.R.A.C.I.'s notebook, work checklist, traffic controller, retry rules, approval pause, quality checker, model directory, machine directory, resource reservation system, workstation protection rules, and a safe limit for how many independent jobs may run together.

### Technical Detail

Accepted Architecture 2 work through Phase 1K includes:

- **Foundation and Phase 1A:** canonical identifiers and records, SQLite persistence, migrations, transactional state-plus-event writes, optimistic versions, immutable history, and hash-chained events.
- **Phase 1B:** guarded Task lifecycle, persisted DAG execution, deterministic verification, and conservative interrupted-work recovery.
- **Phase 1C:** bounded per-Task retries and durable approval pause, approval, and denial behavior.
- **Phase 1D:** atomic complete-graph admission, acyclic validation, canonical persisted Task queue, deterministic scheduling, and queue inspection.
- **Phase 1E:** explicit Architecture 2 runtime composition and non-destructive Architecture 1 state assessment/import as inert legacy history.
- **Phase 1F:** provider/capability records, qualification and health evidence, deterministic resolution, and a caller-configured Ollama Model Provider adapter.
- **Phase 1G:** stable Nodes, offering locations, node health, deterministic resource scheduling, capacity-aware leases, and Attempt node binding.
- **Phase 1H:** caller-invoked configured-node inspection and auditable manual Node administration.
- **Phase 1I:** bounded Windows process snapshots and deterministic workstation availability recommendations.
- **Phase 1J:** explicit evidence-linked application of workstation recommendations with optimistic Node versions and policy ownership.
- **Phase 1K:** bounded concurrent execution, deterministic admission, resource deferral, atomic workflow scheduling plus lease acquisition, independent supervision, and single-flight Orchestrator ownership.

The precise accepted boundaries are in `docs/governance/ADDENDUM_006_ARCHITECTURE_2_PHASE_1A.md` through `ADDENDUM_016_ARCHITECTURE_2_PHASE_1K.md`.

## What Works Today

### Simple Explanation

Engineers can give the Architecture 2 engine a prepared list of jobs with rules such as "finish A before B." The engine can save the list, run eligible jobs, let independent jobs overlap within a fixed limit, reserve suitable machine capacity, retry certain temporary failures, stop for approval, verify results, and reconstruct its notebook after reopening.

The normal desktop window can start and display its existing shell, but it does not yet expose this full engine to the user.

### Technical Detail

Implemented and tested capabilities include:

- Admit and validate an immutable, pre-authored Task graph.
- Persist Goals, Tasks, dependencies, Attempts, Failures, Verifications, approvals, artifacts, events, providers, offerings, qualifications, health evidence, Nodes, locations, scheduling decisions, leases, and workstation policy evidence.
- Evaluate `success` and `completion` dependency conditions and keep predicate dependencies waiting.
- Select ready Tasks by `createdAt` ascending and then Task ID lexical ascending.
- Execute independent ready Tasks concurrently up to a validated `maxConcurrentTasks`; the default is `1`.
- Defer resource-unavailable Tasks without creating an Attempt or using retry budget, while considering later ready Tasks.
- Keep provider execution separate from authoritative verification.
- Retry transient failures within each Task's durable budget; optionally retry verification failure when configured.
- Pause an affected Task for scoped approval while unrelated admitted work continues.
- Resolve qualified provider offerings from durable evidence and invoke a caller-configured Ollama adapter.
- Select eligible healthy active Nodes and atomically acquire capacity leases with workflow scheduling.
- Inspect configured Ollama Nodes when explicitly requested.
- Evaluate local Windows process basenames and explicitly apply fresh workstation availability evidence to Node administration.
- Reopen file-backed SQLite state and reconstruct canonical history.
- Conservatively fail interrupted scheduled/running work whose outcome cannot be proven, without blind replay.

These capabilities are available through code under `src/architecture2/` and the explicit `bootstrapArchitecture2` composition boundary. They are not automatically enabled by normal Electron startup.

## What Does Not Work Yet

### Simple Explanation

The robot has a strong internal job manager, but it cannot yet receive an ordinary request in the desktop window and autonomously carry it from conversation to a finished real-world result. It also cannot safely stop a running job, move it to another machine, or take over automatically when a machine disappears.

### Technical Detail

Not currently implemented or not connected as live product behavior:

- Natural-language goal intake and autonomous planning/replanning.
- Architecture 2 as the default Electron authority or a user-facing Architecture 2 task UI.
- General tool execution for filesystem, shell, browser, email, calendar, documents, deployment, or media workflows.
- Generalized policy engine, standing-policy UX, or approval UI.
- Predicate dependency evaluation.
- User cancellation, cancellation propagation, forced interruption, preemption, or checkpoint resume.
- Node-loss recovery, automatic failover, execution migration, or alternate-node retry.
- Distributed locking, multiple active Orchestrators, remote workers, or high availability.
- Dynamic concurrency optimization, load balancing, priority displacement, or speculative execution.
- Automatic node discovery, background health polling, or scheduler-triggered workstation evaluation/application.
- General failure diagnosis, circuit breakers, governed research, or automatic alternative selection.
- Purpose-specific working, episodic, semantic, procedural, and preference memory.
- Complete observability UI, cost reporting, traces, notifications, voice, productivity integrations, and broad autonomous actions.

Configured Ollama endpoints and test adapters demonstrate boundaries; their existence does not automatically qualify every model or make Architecture 2 the live assistant.

## Runtime Authority

### Simple Explanation

There are currently two layers. Architecture 1 is the simple dashboard that turns on when the application starts. Architecture 2 is the newer engine in the workshop: it can be started deliberately by code and is heavily tested, but the dashboard has not been rewired to drive it yet.

### Technical Detail

`src/main.ts` remains the normal Electron entry point. It creates a `BrowserWindow`, registers a version IPC handler, and loads the existing static UI. It does not bootstrap Architecture 2.

Architecture 2 is isolated under `src/architecture2/`. `src/architecture2/runtime/runtime.ts` exposes caller-configured composition requiring a database path, execution provider, verifier, and optional Orchestrator settings. Architecture 1 JSON state is untrusted compatibility input and may only be explicitly assessed/imported as non-canonical legacy history. It is not promoted into canonical Architecture 2 workflow state.

## Test and Build Status

### Simple Explanation

The assembly checks passed: all automated checks were green, the software compiled, the real database was closed and reopened successfully, and the desktop application stayed running during its startup check.

### Technical Detail

Latest recorded Phase 1K evidence in `docs/logs/TEST_LOG.md`:

- TypeScript validation: PASS.
- Full automated regression suite: **161/161 tests passed across 14 files**.
- Production build: PASS.
- Focused real file-backed SQLite workflow and close/reopen verification: PASS.
- Electron startup smoke: PASS for eight seconds with expected startup output and empty stderr.
- Diff whitespace hygiene: PASS.
- Architecture 1 remained the live Electron authority during smoke verification.

This is recorded verification evidence, not a claim that deferred end-user capabilities exist.

## Known Limitations

### Simple Explanation

If the lights go out while a worker is using an outside tool, G.R.A.C.I. cannot safely know whether that outside action finished. It writes down that the result is uncertain and stops instead of risking doing the action twice. Also, only one traffic controller may manage a workflow engine instance at a time.

### Technical Detail

- Restart recovery intentionally marks unprovable scheduled/running work failed or indeterminate; provider reconciliation is not implemented.
- One authoritative process and one active `run()` call per Orchestrator are required.
- SQLite is the authoritative local store; multi-process orchestration is outside the accepted design.
- Concurrent slot accounting is process-local, while canonical Task/Attempt state remains durable.
- Resource unavailability leaves a Task ready; there is no background dispatcher unless a caller runs or continues the Orchestrator.
- Scheduling priority does not reorder Tasks; Phase 1D ordering remains authoritative.
- Node health and workstation evidence are explicit observations, not continuous monitoring.
- The deterministic execution provider and verifier are test components, not production defaults.
- The Ollama adapter is bounded and non-streaming; it does not provide chat memory, tool calling, vision, embeddings, or automatic qualification.

## Major Remaining Work

### Simple Explanation

The next assembly stages need to teach the robot how to diagnose failures intelligently, choose safe alternatives, remember useful context, expose its engine through the desktop application, and connect real tools. Each stage must retain the notebook, safety checks, and proof that the work was actually completed.

### Technical Detail

Major roadmap areas from Addendum 005 and later deferred boundaries include:

- Governed but not implemented Phase 1L failure diagnosis and recovery disposition, followed later by separately governed circuit breakers, alternatives, and bounded research.
- Slice 5 purpose-specific memory with provenance, correction, privacy, and retention.
- Slice 6 product observability and expanded autonomy.
- Goal intake, planning, replanning, policy enforcement, and approval UX.
- Qualified tool/agent/research providers and real end-to-end workflows.
- Architecture 2 Electron integration and eventual authority cutover under a separately governed phase.
- Later reliability work for cancellation, reconciliation, failover, migration, monitoring, backup/restore, and production hardening.

## Next Architecture 2 Phase

### Simple Explanation

Phase 1K is still the latest completed phase. Phase 1L has now been approved as the rulebook for diagnosing failures and recording the one safe next recommendation, but none of that Phase 1L behavior has been built yet.

### Technical Detail

Architecture 2 Phase 1K remains the latest implemented and accepted phase. Addendum 017 governs Phase 1L, Durable Failure Diagnosis and Recovery Disposition, and approves only controlled future implementation of deterministic durable diagnosis, outcome certainty, existing-policy retry decisions, changed-condition evidence, and one bounded diagnostic disposition. Phase 1L source code and tests have not been implemented, its acceptance verification has not been run, and its advanced recommendations do not authorize failover, alternate-Node retry, reconciliation execution, cancellation, replanning, research, distributed execution, UI work, or Electron authority cutover.

## Reconstruction Pointers

### Simple Explanation

To rebuild understanding, first read the rules, then this status sheet, then the architecture map, and finally the engineering records showing what was tested.

### Technical Detail

Recommended reading order:

1. `AGENTS.md`
2. `docs/governance/MASTER_SYSTEM_SPEC.md`
3. Numbered governance addenda in ascending order
4. `docs/governance/GOVERNANCE_INDEX.md`
5. `CURRENT_STATUS.md`
6. `CURRENT_ARCHITECTURE.md`
7. `docs/logs/DECISION_LOG.md`
8. `docs/logs/DEVELOPMENT_LOG.md`
9. `docs/logs/TEST_LOG.md`
10. `docs/logs/FAILURE_LOG.md`
11. `src/architecture2/` and `tests/architecture2-*.test.ts`
