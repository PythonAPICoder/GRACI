# G.R.A.C.I. Test Log

Record meaningful verification results. Do not duplicate raw automated-test output unless it is useful for diagnosis.

## Entry Template

### YYYY-MM-DD — <Feature / Milestone>

**Build / Revision**

- 

**Test Scope**

- 

**Automated Tests**

- Command:
- Result:

**Runtime / Integration Verification**

- 

**G.R.A.C.I. Launch Verification**

- Startup:
- UI:
- Changed functionality:
- Regression checks:

**Result**

- PASS / FAIL / DEGRADED

**Notes**

---

### 2026-08-10 — Local Coding-Agent Qualification Bake-Off

**Build / Revision**

- Baseline: e9ba707f0753548cc9acb89ca370b55cd8462bab

**Test Scope**

- Controlled isolation qualification bake-off
- Same frozen qualification task for all candidates
- Same 32,768-token context window
- Same independent-review methodology
- Task: extend Ollama integration with read-only `/api/tags` model-inventory support

**Automated Tests**

- Qwen3-Coder 30B:
  - Result: FAIL (Verification reporting integrity)
  - Incomplete recovery after independent verification exposed second inaccurate report
- Qwen3.6 27B:
  - Result: FAIL (Task-continuity / goal-retention)
  - Stopped before implementation on initial attempt and after one recovery prompt
  - No repository changes made
- GPT-OSS 20B:
  - Result: FAIL (Implementation verification)
  - Stopped prematurely with TypeScript syntax errors
  - Complete tests: FAIL
  - Production build: FAIL
  - git diff --check: FAIL
- GLM-4.7-Flash:
  - Result: PASS
  - TypeScript validation: PASS
  - Complete test suite: PASS (28/28 tests)
  - Production build: PASS
  - git diff --check: PASS
  - No forbidden package/config/UI changes

**Runtime / Integration Verification**

- Independent verification scripts executed for each candidate
- Execution environment: RTX 4090 Ollama host
- Qualification repository: isolated and disposable
- Verification scope: functional correctness, instruction/scope compliance, repository understanding, tool execution, multi-file editing, failure recognition, failure recovery, verification discipline, reporting truthfulness, unnecessary changes

**Result**

- PASS: GLM-4.7-Flash qualified. Three candidates not qualified.

**Notes**

- Agent self-reported completion or verification is non-authoritative
- Executable verification remains authoritative: validation -> tests -> build -> runtime
- Independent Architect/Reviewer verification remains required during current development stage

---

### 2026-08-12 — Architecture 2 Foundation Documentation

**Build / Revision**

- Documentation-only working tree based on `5792df3`

**Test Scope**

- Governance precedence and naming
- Required Architecture 2 topic coverage
- Internal heading/link hygiene
- Repository scope compliance
- Whitespace validation

**Automated Tests**

- No application build or runtime tests required because no runtime source, dependency, configuration, or persistent state was changed.
- Required-topic coverage check: PASS (19/19 required sections found).
- Duplicate-heading check: PASS.
- `git diff --check`: PASS.
- Documentation-only scope check: PASS (no changed path outside `docs/`).

**Runtime / Integration Verification**

- Not applicable to documentation-only work.

**G.R.A.C.I. Launch Verification**

- Not required: runtime behavior is unchanged.

**Result**

- PASS

### Phase 1E architectural review correction

- Required execution provider/verifier composition test: PASS through TypeScript validation and explicit deterministic test setup.
- Zero-eligible-record import: PASS; first import created a durable zero-count operation, no history records were inserted, and repeat import returned the original operation.
- Focused Phase 1E/persistence/queue/orchestrator suite: PASS, 67/67 across 4 files.

---

### 2026-08-13 — Architecture 2 Phase 1F Governance Authorization

**Test Scope**

- Governance precedence and next-unused addendum numbering.
- Phase 1F alignment with Addendum 005 Slice 2 and Addendum 010 deferred boundaries.
- Explicit in-scope, deferred-scope, persistence, qualification, resolution, Ollama-adapter, recovery, and acceptance requirements.
- Documentation-only repository scope and whitespace hygiene.

**Verification**

- Product Owner scope approval: PASS.
- Addendum 011 status and precedence entry: PASS.
- Architecture 1 authority and Phase 1F non-goals preserved: PASS.
- No source, test implementation, dependency, configuration, or persistent-state change: PASS.
- Markdown/diff hygiene verification: PASS (`git diff --check`).
- Changed-path scope verification: PASS; only Addendum 011, the Governance Index, and the Decision, Development, and Test logs changed.

**Runtime / Integration Verification**

- Not applicable: this checkpoint changes governance and engineering-history documentation only.

**Notes**

- Phase 1F source implementation is authorized only within the controlled scope of Addendum 011; no source implementation occurred in this documentation checkpoint.

### 2026-08-13 — Architecture 2 Phase 1F Implementation

**Automated Verification**

- TypeScript validation: PASS (`npm.cmd run validate`).
- Full automated regression suite: PASS, 101/101 across 10 files.
- Phase 1F Ollama adapter contract tests: PASS, 7/7.
- Phase 1F resolver tests: PASS, 4/4.
- Production build: PASS; `dist/main.js`, `dist/preload.js`, and `dist/ui/index.html` verified.
- Diff whitespace hygiene: PASS (`git diff --check`).

**Runtime / Integration Verification**

- Local Ollama health: PASS; version `0.32.9` returned by `/api/version`.
- Local Ollama inventory: PASS; 10 models returned by `/api/tags`.
- Real Electron startup smoke: PASS; application emitted `Electron app starting` and remained running for the 15-second smoke window without an uncaught startup error.
- Architecture 1 remained the Electron authority; Phase 1F introduced no automatic Architecture 2 startup or provider registration.

**Coverage**

- Provider health, inventory, generation, timeout, malformed response, HTTP failure, and connection failure normalization.
- Atomic registration/Event rollback, close/reopen reconstruction, qualification and health evidence, deterministic ranking, stable rejection reasons, and selected-offering Attempt persistence.
- Contract, privacy, permission, feature, format, schema, side-effect, qualification fingerprint, health, quality, latency, and cost filtering.
- Existing verification, bounded retry, approval, queue, dependency, legacy import, and interrupted-work recovery regressions.

### 2026-08-13 — Architecture 2 Phase 1G Implementation

**Automated Verification**

- TypeScript validation: PASS.
- Full automated regression suite: PASS, 114/114 across 11 files.
- Focused resource scheduler, persistence, and orchestrator suite: PASS, 54/54.
- Production build: PASS; required Electron output verified.
- Diff whitespace hygiene: PASS.

**Persistence and Scheduling Verification**

- Schema migration 5 and populated prior-state preservation: PASS.
- Atomic node/location registration plus Event rollback: PASS.
- Node, observation, decision, and lease close/reopen reconstruction: PASS.
- Active capacity conflict rejection and release: PASS.
- Missing/stale/unacceptable health, draining/disabled state, privacy, location enablement, and capacity filtering: PASS.
- Deterministic ranking across record insertion permutations: PASS.
- Compute Node persisted on Attempt before provider invocation and lease release after known outcome: PASS.

**Live Verification**

- Local Ollama node: PASS, version `0.32.9`.
- Configured Ollama node: PASS, version `0.32.5`.
- Real Electron startup smoke: PASS; startup reached `Electron app starting` and remained active through the 15-second smoke window without an uncaught startup error.
- Architecture 1 remained the live Electron authority.

### 2026-08-13 — Architecture 2 Phase 1H Implementation

**Automated Verification**

- TypeScript validation: PASS.
- Full automated regression suite: PASS, 123/123 across 12 files.
- Configured-node inspection tests: PASS, 6/6.
- Phase 1H persistence tests included in the 20/20 Architecture 2 persistence suite.
- Production build and diff hygiene: PASS.

**Behavior Verification**

- Successful, empty, partial, and failed health/inventory evidence: PASS.
- Deterministic inventory ordering across response permutations: PASS.
- Evidence excludes endpoint and configuration references: PASS.
- Inspection and administrative history close/reopen reconstruction: PASS.
- All valid non-no-op administrative transitions: PASS.
- Stale version/state, no-op, empty reason, and Event rollback rejection: PASS.
- Existing active leases remain unchanged by manual administrative transitions: PASS.

**Live Verification**

- Local configured Ollama: PASS, version `0.32.9`, 10 models.
- Remote configured Ollama: PASS, version `0.32.5`, 5 models.
- Electron startup smoke: PASS; Architecture 1 remained authoritative.

### 2026-08-13 — Architecture 2 Phase 1I Implementation

**Automated Verification**

- TypeScript validation: PASS.
- Full automated regression suite: PASS, 138/138 across 13 files.
- Workstation workload evaluation tests: PASS, 11/11.
- Architecture 2 persistence suite: PASS, 24/24.
- Production build and diff hygiene: PASS.

**Safety and Behavior Verification**

- Complete, empty, failed, malformed, truncated, and unsupported snapshots: PASS.
- Exact case-insensitive Mod Organizer 2 and configured-game matching: PASS.
- Stable evidence across process/rule permutations: PASS.
- Command lines, arguments, configuration references, and secrets excluded from evidence: PASS.
- Recommendation persistence/reopen, Event rollback, append-only enforcement, and corruption diagnostics: PASS.
- Recommendation evidence leaves Node version/state and active leases unchanged: PASS.

**Live Verification**

- Explicit Windows process snapshot: PASS; 167 process records, 0 Mod Organizer 2 matches at inspection time.
- Electron startup smoke: PASS; Architecture 1 remained authoritative.

### 2026-08-13 — Architecture 2 Phase 1J Implementation

**Automated Verification**

- Focused policy, persistence, scheduler, and evaluation suite: PASS, 55/55 across 4 files.
- TypeScript validation: PASS (`npm.cmd run validate`).
- Full regression suite: PASS, 149/149 across 14 files.
- Production build: PASS; required Electron output verified.
- Diff whitespace hygiene: PASS (`git diff --check`).

**Persistence and Behavior Verification**

- Fresh drain and policy-owned reactivation: PASS.
- Manual drain, disabled Node, inconclusive, stale/mismatched/superseded evidence, and state/version conflict fail closed: PASS.
- Idempotent repeat, durable no-change/rejected decisions, Event rollback, immutable history, corruption diagnostics, and close/reopen: PASS.
- Populated schema 7 to schema 8 migration preserving Node and Phase 1I evaluation records: PASS.
- Existing scheduler blocks draining Nodes and performs no implicit evaluation/application: PASS.

**Live Verification**

- Real Electron startup smoke: PASS; process remained alive for 8 seconds, emitted `Electron app starting`, and stderr was empty.
- Architecture 1 remained the live Electron authority. Phase 1J has no startup, background, or scheduler-triggered behavior.

### 2026-08-14 — Architecture 2 Phase 1K Implementation

**Automated Verification**

- Baseline TypeScript validation: PASS.
- Baseline full regression suite: PASS, 149/149 across 14 files.
- Focused Orchestrator suite: PASS, 39/39 including final composition validation.
- Focused persistence and resource scheduler suite: PASS, 35/35 across 2 files.
- Final TypeScript validation: PASS (`npm.cmd run validate`).
- Final full regression suite: PASS, 161/161 across 14 files.
- Production build: PASS; required Electron output verified.
- Diff whitespace hygiene: PASS (`git diff --check`).

**Concurrency and Durability Verification**

- Independent Tasks overlapped while durably `running`; configured limit remained two: PASS.
- Deterministic admission, dependency gating, single-flight rejection, failure isolation, and approval isolation: PASS.
- Resource-blocked head Task remained ready with no Attempt while later work executed: PASS.
- Atomic Task scheduling, decision, lease, and Event persistence plus capacity-conflict no-op: PASS.
- Existing retry, approval, verification, dependency, queue, workstation policy, and interrupted-work recovery regressions: PASS.
- Focused real file-backed SQLite workflow, close/reopen reconstruction, lease acquisition, capacity conflict, release, and reacquisition: PASS.

**Live Verification**

- Real Electron startup smoke: PASS; process remained alive for 8 seconds.
- Expected `Electron app starting` output present; stderr empty.
- Architecture 1 remained the live Electron authority.

### 2026-08-14 — Living Status and Architecture Documentation

**Verification**

- Documentation-only changed-path scope: PASS.
- Current HEAD, Phase 1K governance, implementation boundaries, and 161/161 recorded test evidence reconciled against repository files: PASS.
- Every major document section pairs a `Simple Explanation` with corresponding technical detail: PASS.
- Implemented, tested, configured, live, and deferred behavior are explicitly distinguished: PASS.
- `README.md` discovery links and referenced repository paths: PASS.
- Governance addenda and governance policy unchanged: PASS.
- Diff whitespace hygiene: PASS.

**Runtime / Integration Verification**

- Not required: documentation-only update; production source, tests, configuration, and runtime behavior are unchanged.

### 2026-08-14 — Architecture 2 Phase 1L Governance Authorization

**Verification Scope**

- Expected repository checkpoint, clean starting worktree, next-unused addendum number, and governance precedence.
- Phase 1L alignment with Addendum 005 Slice 4, current Phase 1K behavior, existing retry and approval semantics, and explicitly deferred recovery boundaries.
- Documentation-only changed paths, implementation-status claims, reference consistency, and whitespace hygiene.

**Runtime / Integration Verification**

- Not applicable: this checkpoint governs future implementation and changes no source, tests, dependencies, configuration, persistence schema, or runtime behavior.

**Result**

- PASS. Addendum 017 is the next unused number and is indexed after Addendum 016.
- PASS. Changed paths are documentation only; no source, test, dependency, configuration, schema, generated output, or `CURRENT_ARCHITECTURE.md` file changed.
- PASS. Phase 1K remains identified as the latest implemented and accepted phase, while Phase 1L is explicitly governed but not implemented.
- PASS. `git diff --check` reported no whitespace errors.

---

### 2026-08-12 — Architecture 2 Phase 1B Workflow Kernel

**Build / Revision**

- Starting checkpoint: `384ad55407263648dfe3c1af3662954052c9245e`.
- No dependency, package manifest, configuration, staging, commit, push, tag, reset, rebase, or history change.

**Test Scope**

- Valid, invalid, evidence-guarded, terminal, and stale-version transitions.
- Required dependency waiting, release, upstream failure blocking, multi-level DAG order, and deterministic independent-task order.
- Distinct immutable Attempts and deterministic numbering.
- Execution success plus verification success/failure and execution failure without false verification success.
- Successful and failed complete workflows.
- Close/reopen non-reexecution, preserved history, continued planned work, and interrupted-running reconciliation.
- State/event and Attempt/workflow atomic rollback.
- Full Phase 1A and Architecture 1 regressions.

**Automated Tests**

- TypeScript validation: PASS.
- Phase 1B focused suite: PASS, 14/14.
- Phase 1A persistence suite: PASS, 11/11.
- Full Vitest suite: PASS, 45/45 across 6 files.
- Production build: PASS after using the documented normal-user context for inherited legacy `dist/services/ollama` ACLs.
- `git diff --check`: PASS.

**Runtime / Integration Verification**

- Compiled Task state machine, Orchestrator, deterministic provider, and verifier loaded under Electron embedded Node: PASS.
- No real AI or network execution introduced by Phase 1B.

**G.R.A.C.I. Launch Verification**

- Real Electron startup: PASS.
- Five-second smoke window: PASS.
- Startup log observed; stderr empty.
- Clean test shutdown: PASS.
- Architecture 1 runtime remains the active composition by design.

**Result**

- PASS

**Final Artifact Inspection**

- Repository SQLite/database/WAL/SHM artifacts: none.
- Generated test artifacts tracked: none.
- Dependency, package manifest, TypeScript configuration, and runtime configuration changes: none.
- Generated `dist` changes: none.
- Forbidden provider/network/model/GPU references in new workflow, execution, and verification source: none.

---

### 2026-08-12 — Architecture 2 Phase 1A Durable Kernel

**Build / Revision**

- Working tree based on `5792df3`; no commit, stage, tag, push, or history change.
- System Node v24.19.0 / SQLite 3.53.3.
- Electron embedded Node v24.18.1 / SQLite 3.53.1.

**Test Scope**

- Migration initialization and persisted schema version.
- Close/reopen durability.
- Foreign-key and identifier/invariant rejection.
- Task dependency persistence and ordering.
- Distinct retry-like Attempt preservation.
- Append-only ordered events and SHA-256 hash chaining.
- Atomic rollback when event insertion fails.
- Optimistic concurrency conflict detection.
- Disposable, isolated test databases.
- Full Architecture 1 regression suite.

**Automated Tests**

- TypeScript validation (`tsc --noEmit`): PASS.
- Focused Phase 1A suite: PASS, 11/11.
- Full Vitest suite: PASS, 31/31 across 5 files.
- Production build (`npm.cmd run build`): PASS after resolving the documented legacy-output ACL issue.
- `git diff --check`: PASS.

**Runtime / Integration Verification**

- Compiled persistence provider executed under Electron's embedded Node: PASS.
- Empty temporary database migrated to schema 1: PASS.
- Close/reopen returned schema 1: PASS.
- Temporary SQLite/WAL/SHM files removed after the test: PASS; none found in repository source, tests, docs, config, or data paths.

**G.R.A.C.I. Launch Verification**

- Startup: PASS; real Electron application remained running through the five-second smoke window.
- Startup log: `[INFO] ... Electron app starting`.
- UI/runtime regression: no startup or stderr failure observed.
- Shutdown: PASS; launched process stopped cleanly after smoke verification.
- Changed functionality: intentionally not wired into Architecture 1 runtime during Phase 1A.

**Result**

- PASS

**Notes**

- Expected error logs from mocked Ollama failure/timeout tests are not test failures.

---

### 2026-08-13 — Architecture 2 Phase 1C

- Baseline `npm.cmd run validate`: PASS.
- Focused Orchestrator suite after correction: PASS, 19/19.
- Covered transient success retry, retry exhaustion, restart after exhaustion, permanent failure, verification failure, approval pause, restart while paused, explicit approval/resume, invalid approval, and Phase 1B indeterminate recovery regression.
- Final TypeScript validation: PASS.
- Full Vitest regression suite: PASS, 50/50 across 6 files.
- Production build: PASS after the documented authenticated-user ACL rerun; no source workaround.
- Real Electron runtime smoke: PASS; alive after five seconds, expected startup log present, stderr empty, test process stopped.
- `git diff --check`: PASS; no repository SQLite/WAL/SHM artifacts found.

### 2026-08-13 — Phase 1C targeted acceptance corrections

- TypeScript checkpoint: PASS.
- Focused Architecture 2 persistence and Orchestrator suites after fixture correction: PASS, 36/36.
- New coverage: retry recovery revalidation/fail-closed behavior, sensitive-transition authorization, positive verification retry, verification retry exhaustion, denial persistence/restart, invalid denial, and populated schema-1 migration.
- Final full regression, build, runtime smoke, and repository checks follow this entry.
- Final `npm.cmd run validate`: PASS.
- Final `npm.cmd test`: PASS, 56/56 across 6 files.
- Final authenticated-user `npm.cmd run build`: PASS.
- Electron five-second runtime smoke: PASS; process remained alive, startup log present, stderr empty, test process stopped.

---

### 2026-08-13 — Architecture 2 Phase 1D Durable Work Queue

**Build / Revision**

- Starting checkpoint: `b0762d48434428df5743c5c42dc9cae6ed846156` on clean synchronized `main`.
- No dependency, package manifest, runtime configuration, Architecture 1, UI, staging, commit, or push change.

**Test Scope**

- Atomic complete graph admission, rollback, retrieval, and file-backed reconstruction.
- Deterministic Kahn graph validation, unknown/duplicate/conflicting/self dependency rejection, cycles, downstream unresolved diagnostics, diamond DAGs, and multi-level DAGs.
- Ready-only scheduling by `createdAt` and Task ID independent of input order and restart.
- Success, completion, predicate-waiting, direct failure, and transitive failure dependency behavior.
- Deterministic queue inspection including predecessor states, blockers, Attempts, Failures, and terminal reasons.
- Explicit malformed JSON, enum, timestamp, missing predecessor, and interrupted-state diagnostics.
- Existing transition, optimistic concurrency, atomic event, retry, approval, terminal replay, and interrupted-running recovery regressions.

**Automated Tests**

- Baseline full suite: PASS, 56/56.
- Focused Phase 1D/persistence/orchestrator suite: PASS, 58/58 across 3 files.
- Final TypeScript validation (`npm.cmd run validate`): PASS.
- Final full Vitest suite (`npm.cmd test`): PASS, 78/78 across 7 files.
- Production build (`npm.cmd run build`): PASS.
- `git diff --check`: PASS after correcting two trailing-whitespace findings.

**Runtime / Integration Verification**

- Compiled Phase 1D persistence and queue inspection executed against a real temporary file-backed SQLite database: PASS.
- Graph admitted, database closed, reopened, inspected in deterministic Task-ID tie-break order, and temporary database/WAL/SHM files removed: PASS.

**G.R.A.C.I. Launch Verification**

- Real Electron startup: PASS.
- Five-second smoke window: PASS.
- Expected `Electron app starting` log present; stderr empty.
- Test process tree stopped after verification.
- Architecture 1 remains the live composition by design; no Phase 1D UI or runtime integration was introduced.

**Result**

- PASS

---

### 2026-08-13 — Architecture 2 Phase 1E Runtime Composition and Legacy Import

**Build / Revision**

- Expected baseline and starting HEAD: `532cc8ebad365e000b4d73c0bf10857af079835e`.
- Starting working tree: clean.

**Test Scope**

- Valid, empty, malformed, partial, unsupported, and ambiguous Architecture 1 state.
- Deterministic assessment ordering, reasons, and SHA-256 provenance.
- Non-destructive source handling and completed-state non-promotion.
- Repeated import idempotency and durable provenance.
- Explicit Architecture 2 bootstrap, real SQLite migration, close/reopen, and reconstruction.
- Complete Phase 1A through Phase 1D and Architecture 1 regressions.

**Automated Tests**

- Baseline `npm.cmd run validate`: PASS.
- Baseline `npm.cmd test`: PASS, 78/78.
- Focused Phase 1E/persistence/queue/orchestrator suite: PASS, 66/66 across 4 files.
- Final `npm.cmd run validate`: PASS.
- Final `npm.cmd test`: PASS, 86/86 across 8 files.
- `npm.cmd run build`: PASS.
- `git diff --check`: PASS.

**Runtime / Integration Verification**

- Real temporary file-backed SQLite schema 3 bootstrap: PASS.
- Explicit import, clean close, reopen, operation/history reconstruction: PASS.
- Source bytes unchanged after assessment and repeated import: PASS.

**G.R.A.C.I. Launch Verification**

- Real Electron process alive after five seconds: PASS.
- Expected `Electron app starting` log present; stderr empty.
- Process tree stopped after smoke verification.
- Architecture 1 remained the active default runtime; no Architecture 2 Electron wiring was added.

**Result**

- PASS
