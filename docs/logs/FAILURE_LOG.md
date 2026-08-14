# G.R.A.C.I. Phase 1 — Autonomous Recovery and Continuation

## 2026-08-14 - Phase 1T Current-Schema Fixture Correction

- The first related regression run passed provider resolution but Phase 1R retained a schema-16 assertion and its synthetic schema-14 rollback left the new schema-17 table in place.
- Updated current-version assertions to 17 and made the synthetic rollback remove schema-17 objects before migration replay. No production migration defect was present.

## 2026-08-14 - Phase 1R TypeScript Collection Declaration Correction

- Initial TypeScript validation rejected `readonly Array<...>` because TypeScript permits the `readonly` modifier only on array and tuple literal types.
- Replaced it with the equivalent `ReadonlyArray<...>` declaration in `ResearchRequestInspection`.
- TypeScript validation and the focused Phase 1R suite passed after correction.

## 2026-08-14 - Phase 1R Current-Schema Assertion Correction

- The first focused regression run passed Phase 1R but three prior suites retained hard-coded schema-14 current-version assertions and failed after the governed schema-15 migration.
- Updated all current-schema assertions to 15 without changing fixtures that intentionally simulate older source schemas.
- The same focused regression set passed after correction.

## 2026-08-14 - Phase 1R Synthetic Schema-12 Fixture Correction

- The first broad recovery regression failed because the Phase 1P synthetic schema-12 downgrade removed schema-13 and schema-14 objects but retained new schema-15 research indexes.
- The failure was confined to the test fixture; a genuine schema-14 database cannot already contain schema-15 indexes.
- Updated the fixture to remove all schema-15 research tables and indexes before replaying migrations. The recovery/replanning set then passed 62/62, and the full suite passed 225/225.

## 2026-08-14 - Phase 1Q Schema Baseline Fixture Correction

- Regression tests initially retained schema-13 expectations and one schema-12 fixture left schema-14 metadata/tables present.
- Root cause was stale test baseline/setup after the required schema advance, not migration or runtime behavior.
- Updated assertions to schema 14 and removed both schema-13 and schema-14 objects in the simulated old database before retesting.
- The first Electron smoke wrapper hung on redirected child handles after terminating its `npm` parent; direct Electron invocation replaced the harness and passed with clean stderr.

## 2026-08-14 - Phase 1P Transactional Authority Race Correction

**Failure**

- Review found that pre-transaction input-revision authority checks could race a concurrent approval, Task supersession, or other authority-changing write.

**Root Cause**

- The initial design treated trusted-core checks performed before the SQLite write transaction as sufficient authorization, leaving a time-of-check/time-of-use window before revision and Task state were committed.

**Correction**

- Reconstructed and revalidated the complete Task, latest Attempt, latest Failure, current diagnosis, conflicting recovery, pending approval, Attempt-limit, prior-input, exact mutation, optimistic-version, and Event gates inside the same `BEGIN IMMEDIATE` transaction that writes the immutable revision and Task update.
- Expanded tests to exercise authority changes at the persistence boundary and require fail-closed behavior without a revision or Task mutation.

**Regression Result**

- Dedicated Phase 1P suite passed 9/9; relevant Phase 1L through Phase 1O regressions passed 45/45 and the full suite passed 217/217.
- TypeScript validation, production build, runtime/import checks, schema migration/reopen, Electron startup, and diff hygiene passed.
- The first Electron smoke wrapper reported the controlled post-smoke exit code instead of the five-second liveness sample. A corrected direct-process wrapper recorded the application alive at five seconds with the expected startup log and empty stderr, then stopped the process tree.

---

## 2026-08-14 - Phase 1O Probe Authority and Verification Attribution Correction

**Failure**

- Independent review found that the initial half-open probe authorization was not consumable or bound to the exact routed Attempt, allowing authority to be represented without proving which execution used it.
- Initial close handling also accepted Verification attribution too weakly and did not sufficiently prove that the passing Verification belonged to the probe-authorized Attempt.

**Root Cause**

- Probe authorization was modeled primarily as circuit-state permission rather than one-time durable execution authority.
- Outcome validation checked the Verification result without a complete persisted chain from probe to provider/resource decision, Task, Attempt identity/number, offering, Node/location, and the Verification's Attempt.

**Correction**

- Added durable `active -> claimed -> consumed` probe status and atomic one-claim enforcement.
- Bound claims to exact provider-resolution or resource-scheduling decisions and exact Task, Attempt, offering, Node, and location identities.
- Added Attempt-start validation against the claimed probe and rejected route/probe reuse.
- Required a persisted passing normal Verification for the exact successful bound Attempt to close; required a current qualifying Phase 1L diagnosis for the exact failed bound Attempt to reopen.

**Regression Result**

- Dedicated Phase 1O suite passed 11 tests, including single-use claim, exact Attempt binding, unrelated Verification rejection, qualifying reopen, schema-12 migration, and close/reopen reconstruction.
- Relevant regressions passed 50 tests; full suite passed 208/208 across 18 files.
- TypeScript validation, production build, and diff hygiene passed. Final Electron/runtime launch evidence remains pending and is not claimed.

---

## 2026-08-14 - Phase 1N Reconciliation Corrections

- The initial `proven_not_completed` schema constraint incorrectly required retry authorization even when the existing Attempt budget or approval gate withheld it.
- The constraint was corrected so the trusted conclusion and evidence persist without creating execution authority; a fresh Attempt remains available only when all existing gates permit it.
- The initial Electron smoke wrapper was interrupted by the harness, not the application. Electron remained alive and startup logs proved normal startup with empty stderr; the process tree was then cleaned.
- Final focused result was 118/118 across 7 files, including 14 Phase 1N tests. Full regression passed 197/197 across 17 files; build, validation, runtime import, reopen, and diff checks passed.

---

## 2026-08-14 — Phase 1M Authority Ordering Correction

- Initial Phase 1M recovery authorization inferred the latest diagnosis from deterministic history ordering that could use hashed diagnosis IDs as a tie-break across equal timestamps.
- Focused Node and failed-recovery scenarios exposed that this did not prove authority for the latest Attempt.
- Recovery now anchors to the latest immutable Attempt, selects the latest Failure for that exact Attempt, and requires the current Phase 1L policy/version diagnosis for that Failure.
- Focused recovery, diagnosis, resolver, and scheduler verification passed 35/35 after correction.

---

## 2026-08-14 — Phase 1L Verification Corrections

- The first full regression run passed 152/161 tests. All nine failures were current-schema assertions still expecting version 8 after migration 9 correctly initialized schema version 9. The affected fixtures were updated; no runtime migration defect existed.
- The first focused Phase 1L run passed 70/71 tests. Two diagnoses created at the same controlled timestamp were ordered by deterministic hashed diagnosis ID rather than causal Attempt order, reversing the expected history projection. Diagnosis inspection now orders by durable Attempt number, then diagnosis timestamp and ID.
- A later full hardening run passed 167/168 tests after diagnosis/Event consistency checks were added. Equivalent idempotent repetition was incorrectly validating an unused new Event before returning the existing diagnosis. Existing-authority comparison now occurs first; equivalent repetition returns the immutable record without a duplicate Event, while conflicting evidence still fails.
- Independent review found that explicit historical diagnosis counted Attempts created after the target Failure and that contradictory category/classification/Attempt evidence was not fully rejected. Diagnosis now uses the causal Attempt number, validates coherent evidence combinations, bounds and sanitizes changed-condition references, and revalidates Event, Verification, Approval, and offering-location attribution after reopen.
- The first review-hardening focused run then exposed two test-fixture assumptions: a Failure was selected by same-timestamp lexical order instead of its diagnosis link, and a changed-condition Event used the generic test aggregate type. The fixtures were corrected without changing runtime semantics.
- Final focused result: 92/92 tests passed across 5 files. Final full result: 169/169 tests passed across 15 files.

---

## 2026-08-13 — Phase 1J Transaction and Corruption Fixture Corrections

- The first focused Phase 1J run failed 8 tests because the new application row referenced its audit Event before that Event was inserted in the same transaction. SQLite foreign-key enforcement correctly rolled back every attempt. The Event insertion was moved before dependent rows within the same atomic transaction; focused behavior then passed except for one fixture.
- The corruption fixture attempted to set a version below the schema constraint, so SQLite rejected the corruption before reconstruction and left the direct test handle open. The fixture now uses a constraint-valid but semantically inconsistent resulting version, and reconstruction explicitly validates transition-version relationships.
- Final focused result after corrections: 55/55 tests passed across 4 files.

---

## 2026-08-13 — Phase 1G Verification Fixture Corrections

- The new orchestrator lease test initially failed because the existing test module did not import Vitest's `vi` helper. The import was added and the focused Phase 1G suite passed 54/54.
- The first full regression run exposed a Phase 1E runtime assertion still fixed at schema version 4. Phase 1G migration 5 correctly returns version 5; the stale assertion was updated without changing runtime behavior.

## 2026-08-13 — Phase 1H Schema Fixture Correction

- The first Phase 1H full regression run found the runtime-import fixture explicitly expecting schema version 5. Migration 6 correctly returned version 6.
- The stale expected version was updated; no runtime or migration behavior required correction.

## 2026-08-13 — Phase 1I Schema Fixture Correction

- The Phase 1I full regression run found the runtime-import fixture still explicitly expecting schema version 6.
- Migration 7 correctly returned version 7. The fixture expectation was updated; runtime and migration behavior were unchanged.

---

## 2026-08-13 — Phase 1F Missing-Evidence Serialization

### Failure

- A resolver test with no qualification or health evidence failed while persisting `candidates_json` with SQLite `CHECK constraint failed: json_valid(candidates_json)`.

### Root Cause

- Candidate projection explicitly included optional fields with `undefined`. The canonical JSON helper produced a non-JSON value for that array instead of omitting absent properties.

### Correction and Verification

- Resolver candidate construction now omits absent qualification and health fields.
- Focused resolver suite passed 4/4 after correction.
- Full regression suite passed 101/101 and the production build passed.

---

## 2026-08-13 — Phase 1E Verification Fixture and Smoke Harness Corrections

**Failure**

- The first focused run found three persistence tests still expecting schema version 2 and one new expected reason list with two keys out of lexical order.
- The first Electron smoke script tried to read redirected logs while the live Electron process still held the files.

**Root Cause**

- Test expectation drift after adding migration 3 and a mistaken manual ordering in the new fixture.
- Smoke-harness shutdown/log-read ordering, not an application startup defect.

**Correction**

- Updated only the current schema expectations and deterministic expected order.
- Stopped the Electron process tree before reading redirected logs.

**Regression Result**

- Focused Architecture 2 suite passed 66/66.
- Final TypeScript validation, 86/86 full tests, production build, SQLite reopen reconstruction, Electron smoke, and diff hygiene passed.

---

## 2026-08-12 — Phase 1B Interrupted-Recovery Evidence Ordering

**Failure**

- After adding the evidence guard for `running -> failed`, one focused restart test failed because the Task transition was prepared before the recovered Attempt was represented as `indeterminate`.

**Root Cause**

- Recovery supplied the original running Attempt to a guard that correctly requires failed or indeterminate Attempt evidence.

**Correction**

- Constructed the indeterminate Attempt first and supplied it to the centralized state machine before the atomic recovery transaction.

**Regression Result**

- Phase 1B focused suite: 14/14 passed.
- Full repository suite: 45/45 passed.

---

## 2026-08-13 — Phase 1D Verification Corrections

**Failure**

- The first TypeScript checkpoint rejected a queue reason projection because raw `blocked` was not part of the machine-readable inspection reason union.
- The first `git diff --check` found trailing whitespace on two added SQLite statement lines.

**Root Cause**

- The projection helper did not explicitly map canonical `blocked` to `required_dependency_failed`.
- Two template-literal closing lines retained spaces from the patch formatting.

**Correction**

- Added the explicit blocked-state reason mapping without changing persisted lifecycle vocabulary.
- Removed the two whitespace defects.

**Regression Result**

- Focused Phase 1D, persistence, and orchestrator tests passed 58/58.
- Final TypeScript validation, 78/78 full tests, production build, runtime verification, and diff hygiene passed.

---

## 2026-08-12 — Phase 1A Malformed-Identifier Test Fixture

**Failure**

- Initial focused persistence test result: 9 passed, 1 failed.
- The invalid identifier was rejected while the fixture called `asIdentifier`, before the assertion invoking persistence.

**Root Cause**

- The fixture accidentally used the production validation helper to construct deliberately invalid input.

**Correction**

- Constructed the deliberately malformed typed value directly so the persistence boundary was exercised.

**Regression Result**

- Focused persistence suite passed 11/11 after correction and addition of optimistic-concurrency coverage.
- No production defect or runtime artifact resulted.

---

## 2026-08-12 — Legacy Build Output ACL Mismatch

**Failure**

- The first production build could not overwrite six existing files under `dist/services/ollama` and returned TypeScript `TS5033` with `EPERM`.

**Root Cause**

- The legacy compiled files were owned by the Administrators group and lacked the explicit sandbox-account ACL present on other build outputs. No Electron process was holding the files, and their read-only attribute was false.

**Correction**

- Reran the unchanged `npm.cmd run build` command using the normal authenticated-user context authorized for that command.
- No source, dependency, or build-configuration workaround was introduced.

**Regression Result**

- Production build passed and emitted all required output.
- The real Electron application launched successfully after the build.

---

## Repository Analysis

I have completed a comprehensive analysis of the repository structure and current state:

1. The working directory is at `E:\GRACI`
2. This is an Electron-based TypeScript application for G.R.A.C.I.
3. The project includes:
   - Core components: configuration, logging, state management, tasks
   - Registry systems: capability, model, node, and tool registries
   - UI structure with HTML templates
   - Tests for core functionality

## Current Implementation Status

The code shows significant progress on Phase 1 foundation components:

### Implemented:
- Electron application entry point (`src/main.ts`)
- Logging system with Winston
- Task management system
- Registry systems (capability, model, node, tool)
- Configuration loader with defaults
- Test suite

### Issues Identified:
- TypeScript compilation is missing (tsc not found)
- Package.json contains module syntax but build dependencies require Node resolution
- Some files have incomplete content or require proper import paths
- No full application bootstrap or initialization logic

## Recovery Actions Taken
1. Created a complete `src/main.ts` implementation based on existing patterns
2. Verified that TypeScript compiler and NodeJS can be installed if needed
3. Identified the root cause of build problems: module resolution mismatch in tsconfig

## Next Steps for Completion

Based on the initial requirements, I will now:
1. Configure proper module resolution to support both ESM and TS compilation
2. Verify the current structure works with Node.js modules
3. Test that all components load properly and initialize without errors
4. Build a working electron application using available tools
5. Conduct runtime verification to confirm functionality

---

## 2026-08-13 — Phase 1C Verification Corrections

- `vitest --runInBand` failed because Vitest 3 does not support that Jest option. Correct command: `npm.cmd test`.
- The first post-migration suite expected schema version 1 in two assertions. Updated them to current schema version 2.
- Approval resume initially emitted an undefined optional reason in an audit payload, rejected by SQLite `json_valid`. Normalized absent reasons to JSON `null`; focused tests and validation passed.

### 2026-08-13 — Acceptance-correction fixture

- The first populated migration test reused the already initialized current-schema database and failed with `table schema_migrations already exists`; the open raw handle also prevented temporary cleanup.
- Root cause: fixture path selection, not migration behavior.
- Corrected the fixture to create a separate `legacy.sqlite` schema-1 database. Focused persistence and Orchestrator suites then passed 36/36.

I am following the recovery procedure by:
- Inspecting → Diagnosing (finding TypeScript/module issues) → Correcting (fixing main.ts) → Building (with existing dependencies) → Testing (unit tests in place)
