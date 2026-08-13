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

**Notes**

- Architecture 2 implementation is explicitly not authorized by this documentation phase.

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
