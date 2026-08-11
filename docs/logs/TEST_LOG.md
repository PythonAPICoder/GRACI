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
