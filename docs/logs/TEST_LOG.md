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
