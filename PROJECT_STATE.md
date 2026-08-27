# GRACI Project State

This document and the durable files in this repository are the authoritative source of GRACI project state. Conversation history is not project state.

## Project and phase

GRACI is a local-first AI workload orchestration project. It will coordinate inference resources while preserving safe availability rules and the ability to operate entirely on the primary host.

## Build progress

- Overall Build: Phase 2 complete
- Completed Phase: Phase 2 — Autonomous Loop
- Completed Stage: Phase 2C — Autonomous Loop Acceptance & Closure
- Previous Accepted Phase: Phase 1 — Minimal GRACI Core
- Next Authorized Phase: Phase 3 — Resource / Model Router

Phase 1A through Phase 1D and Phase 2A through Phase 2C are accepted. Phase 2 is
implemented, verified, closed, and committed by the closure commit containing this
state. Phase 3 is authorized but has not begun.

## Phase 2C acceptance and closure

- The integrated deterministic suite covers direct and multi-file success,
  ineffective repair followed by feedback and successful repair, repair/iteration/
  model-call/inspection/modification exhaustion, malformed responses, independently
  evaluated policy violations, progress guards, provider/tool failures, false model
  success, and complete ordered evidence. The warning-strict suite passes 58 tests,
  including every Phase 1, Phase 2A, and Phase 2B regression.
- The acceptance audit repaired two in-scope defects: post-failure repair budget
  enforcement had incorrectly depended on total pre-test writes, and unexpected
  governed execution exceptions could leave the terminal reason unset. Regression
  tests cover both repairs.
- Live run `218d2969-cd66-44b2-bab0-073abecdf975` used only
  `http://127.0.0.1:8080/v1` and server-reported `qwen3.8-27b-q4_k_m`. In seven
  cycles Qwen listed scope, inspected three related files, made two governed
  replacements, and passed two deterministic tests. Evidence is under
  `phase2c/evidence/`; the fixture was automatically removed.
- Compilation, JSON validation for all six accepted evidence records, diff checks,
  safety review, evidence review, documentation review, and secret-pattern review
  passed. No 4090 or cloud workload occurred.

## Phase 2B implementation and acceptance

- The Phase 2A explicit state machine now supports governed `list_files`, multi-file
  inspection, multiple independently validated file replacements, test feedback,
  bounded repair, and retest. Every cycle separately records schema, action,
  workspace, policy, and budget validation before tool execution.
- Defaults are 12 iterations, 12 model calls, 6 inspections, 4 modifications, 2
  post-failure repairs, a 30-second command timeout, 12,000 characters per
  model-visible evidence field, 6 recent cycles, and a 2-action identical-repeat
  allowance. Evidence shows both consumption and remainder.
- Context contains only the configured file lists, test directory, budget state,
  and bounded recent completed cycles. Truncation events are explicit. Deterministic
  guards stop a third identical action, retesting a known failure without a change,
  and premature finish attempts.
- The warning-strict suite passes 50 tests. Phase 2B coverage proves multi-file
  inspection and two writes, failure feedback and repair, invalid second-action
  rejection, budget enforcement, progress guards, evidence ordering, and model
  claims unable to override deterministic tests. All Phase 1/2A tests pass.
- Live run `cf3c6de8-1bf7-404b-8ff2-c521d6d0776a` used only
  `http://127.0.0.1:8080/v1` and server-reported `qwen3.8-27b-q4_k_m`. In 7 cycles
  Qwen inspected three files, made two governed replacements, and passed both
  deterministic tests. Evidence is under `phase2b/evidence/`; the fixture was
  automatically removed.
- Security review confirmed prior containment, sensitive-path, `.git`, fixed-command,
  local provider/model, no-shell, no-Git-mutation, and no-package/network/system
  boundaries remain intact. No 4090 or cloud workload occurred.

## Phase 2A implementation and acceptance

- `graci.autonomous.AutonomousRepairController` runs one synchronous state machine
  in an existing disposable non-Git workspace. Each cycle obtains one local-model
  decision, validates its exact schema, validates policy independently, invokes a
  controlled tool, persists evidence atomically, and either continues or terminates.
- The only model actions are `inspect_file`, `write_text`, `run_tests`, and `finish`.
  Reads and writes require caller-supplied exact file allowlists; editable files must
  be a subset of readable files. Tests use the existing fixed unittest command.
- Default limits are 8 reasoning/action iterations, 2 repair writes, and a 30-second
  test timeout. Limits are host configuration, never model input. Exhaustion and all
  malformed, unsupported, policy-violating, provider, tool, and verification cases
  terminate as FAIL.
- Only a consistent governed test result with command success, exit code 0, no
  timeout, and PASS fields can establish final PASS. Model assertions and `finish`
  cannot override deterministic evidence. The last three completed cycles are fed
  back, with file and test streams truncated to 12,000 characters for model context;
  complete evidence remains in the durable record.
- The warning-strict suite passes 43 tests, including direct repair, a failed first
  repair followed by a successful second repair with test feedback, repair and
  iteration exhaustion, malformed/unsupported decisions, policy violations, tool
  and provider failures, false success resistance, deterministic evidence
  inconsistency, and multi-cycle persistence. All 32 Phase 1 tests still pass.
- Live run `2dede672-a6cf-4285-9b9f-505cb296fce6` used only
  `http://127.0.0.1:8080/v1` and server-reported model
  `qwen3.8-27b-q4_k_m`. Qwen inspected both allowlisted files, replaced only
  `calculator.py`, requested tests, and received deterministic exit code 0. The
  temporary fixture was automatically removed; durable evidence is under
  `phase2a/evidence/`.
- The first live attempt correctly failed closed before tool execution because Qwen
  emitted Markdown fences. The prompt was clarified while strict parsing remained
  unchanged; the failed preliminary record was removed as a debug artifact.
- Security regression review confirmed workspace containment, traversal/absolute
  outside-path rejection, sensitive and `.git` blocking, command allowlisting,
  absence of Git mutation, package/network/system operations, fixed endpoint/model,
  and enforced iteration/repair limits. Governed Python commands now disable bytecode
  writes and fix the hash seed to avoid stale disposable-fixture bytecode and improve
  determinism.

## Phase 1D acceptance and closure

- The deterministic integrated acceptance suite covers a valid end-to-end action,
  malformed/schema-invalid output, outside-workspace policy rejection,
  deterministic verification mismatch despite model success wording, injected
  controlled-tool failure, and durable evidence integrity for PASS and FAIL.
- The complete warning-strict suite passes 32 tests. Python compilation and Git
  whitespace/diff checks pass.
- Live run `315228d2-3413-4a8b-b059-2c3efc727ac7` used only the fixed localhost
  endpoint and `qwen3.8-27b-q4_k_m`. It validated and executed one controlled write
  in the isolated Phase 1D sandbox, then established PASS by exact read-back.
- The safety audit found and repaired one configuration defect: Phase 1 previously
  accepted any non-empty model name. Configuration now rejects every model except
  `qwen3.8-27b-q4_k_m`, with regression coverage.
- Durable closure details, live evidence, and the verified output are under
  `phase1d/`. No 4090 workload, cloud AI, external network access, dependency
  installation, secret storage, or system modification occurred.

## Phase 1C implementation

- `graci.vertical_slice.VerticalSliceController` integrates the Phase 1A local
  provider with the Phase 1B controlled tool layer for one synchronous bounded text
  file create/update in an existing explicitly configured sandbox.
- The caller fixes one allowed relative target. The model returns exactly
  `schema_version`, `action`, `target_path`, `content`, and `rationale`, and only
  `write_text` is supported. Strict schema validation and exact-target/workspace/
  sensitive-path policy validation occur before tool execution and fail closed. A
  Git repository root cannot be selected as the Phase 1C workspace, and `.git`
  paths are prohibited.
- The controlled tool writes atomically and GRACI independently reads the target.
  Exact expected/observed content equality, never a model assertion, determines
  PASS. Evidence records the task, fixed provider/model/endpoint, proposed action,
  validation, tool result, verification, final status, errors, and UTC timestamps.
- CLI callers select Phase 1C with both `--workspace` and `--target`; omitting both
  preserves the Phase 1A task interface.

## Phase 1C verification

- Warning-strict offline suite: 26 tests pass. Phase 1C coverage includes valid,
  malformed, unsupported, traversal/outside, and sensitive actions; successful
  controlled modification; verification success/failure; tool failure; truthful
  PASS/FAIL; durable evidence; and model success text unable to override failed
  deterministic verification.
- Live run `626af57f-f32a-4563-8af1-7f2a7b02b019` used only
  `http://127.0.0.1:8080/v1` and server-reported model
  `qwen3.8-27b-q4_k_m`. Schema and policy checks passed, the controlled tool wrote
  43 bytes to the isolated `phase1c/live-sandbox/result.txt`, and exact read-back
  verification passed. Durable evidence is under `phase1c/evidence/`.
- No 4090 workload, cloud AI, external network action, package installation,
  model-generated shell, Git mutation by the model, secret storage, or system
  configuration change occurred.

## Phase 1B implementation

- `graci.tools.ToolLayer` exposes deterministic programmatic interfaces for UTF-8 directory listing, text reads, atomic text creation/replacement, approved local commands, repository test execution, and read-only Git status/diff/log/HEAD observation.
- Every operation returns a structured result containing the tool and request, success, UTC start/end timestamps, error classification/message, and relevant resolved paths, process output, exit code, or timeout state.
- Workspace paths are resolved before use and must remain under the configured workspace. Traversal, absolute outside paths, symlink escapes, credential/secret path names, binary reads, and outside-workspace writes fail closed.
- Commands use executable/argument arrays with `shell=False`, a workspace-contained working directory, captured UTF-8 output, timeouts, and exit-code-based truth. The allow policy is limited to Python version checks, warning-strict unittest discovery within the workspace, and fixed read-only Git commands.
- Git observation disables system/global Git configuration, prompts, optional locks, fsmonitor, external diff, and text conversion. There are no commit, staging, checkout, reset, clean, branch mutation, push, package-manager, network, elevation, or system-configuration tools.
- The tool layer is exported beside the existing controller but is not available to a model-driven autonomous loop. That loop remains Phase 1C work.

## Phase 1B verification

- Offline suite: 18 tests pass with warnings treated as errors using `python -W error -m unittest discover -s tests -v`.
- Tests cover file create/read/replace/list, missing and binary files, traversal and absolute outside-path rejection, sensitive-path rejection, allowed/disallowed commands, timeout and stdout/stderr capture, truthful passing/failing test results, outside test-discovery rejection, and successful Git status/diff/log/HEAD reads in a temporary repository.
- Controlled local validation in a temporary repository-local sandbox created/read/replaced a file, ran `python --version`, passed a one-test unittest suite, read Git status, and rejected an attempted `../PROJECT_STATE.md` read. The sandbox was removed afterward.
- No 4090 workload, cloud AI, external network operation, dependency installation, secret storage, or system configuration change occurred.

## Phase 1A implementation

- `python -m graci "<task>"` submits one text task to the controller.
- Phase 1A configuration permits only the primary 3090 endpoint at `http://127.0.0.1:8080/v1`.
- The local llama.cpp provider uses the OpenAI-compatible chat-completions API and model `qwen3.8-27b-q4_k_m`.
- Model output must be one JSON object containing exactly `schema_version`, `status`, and `summary`. Invalid envelopes, malformed output, field/type/value errors, model identity mismatches, HTTP failures, and model-reported failures all fail closed.
- Every accepted task gets a UUID run ID and an atomically written JSON record under `runs/`, including task, UTC timestamps, provider/node/endpoint/model identity, HTTP status, validated result, final status, and errors.
- Runtime run records are intentionally ignored by Git. The accepted live evidence is versioned under `phase1a/evidence/`.
- Implementation uses only the Python standard library and stores no credentials.

## Phase 1A verification

- Offline suite: 8 tests pass with warnings treated as errors using `python -W error -m unittest discover -s tests -v`.
- Live integration run `d7e604aa-318d-47de-a735-966132894d6b` returned HTTP 200 from the localhost 3090 endpoint, reported the configured Qwen model, passed strict contract validation, and produced durable evidence.
- The Phase 1A configuration rejects the 4090 LAN endpoint and cloud endpoints. No 4090 or cloud workload was sent.
- Detailed evidence and the accepted record are under `phase1a/`.

## Current limitations

- One task is executed synchronously per CLI invocation.
- There are no provider retries, reviewers, resource scheduling, cloud escalation,
  authentication, service/API wrapper, or 4090 execution path.
- Tool execution is synchronous and intentionally narrow. It has no recursive deletion,
  arbitrary shell, package management, network command, Git mutation, file patch/diff
  primitive, or streaming output. Phase 2A bounds model feedback, but durable tool
  records retain complete output.
- Phase 2B supports bounded multi-step repair but no independent reviewer, multi-model
  adjudication, general planning, dynamic tool discovery, Git operations, routing,
  scheduling, memory, service/API wrapper, or automatic workspace/parent creation.
- Repair uses complete-file atomic replacement, not a patch primitive. The caller
  must enumerate readable/editable files and provide the deterministic test directory.
- The unresolved 4090 process-detection blocker remains fail-closed.

## Qualification status

- Workspace file operations, direct command execution, Python 3.14.7, and Git 2.55.0.windows.3 passed qualification.
- The 3090 and 4090 llama.cpp model-list endpoints both returned HTTP 200 during Gate 0.
- G0.9 proved structured delegation to local Qwen through the 3090 endpoint, including programmatic JSON parsing and validation.
- Durable qualification evidence is stored under `gate0/`.

## Authoritative architecture constraints

- The 3090 PC is the primary GRACI host and must be capable of running GRACI independently.
- The 3090 local llama.cpp endpoint is `http://127.0.0.1:8080/v1`.
- The 4090 PC is optional enhanced compute capacity.
- The 4090 llama.cpp endpoint is `http://192.168.0.101:8080/v1`.
- Both llama.cpp installations currently expose:
  - `qwen3.8-27b-q4_k_m`
  - `GLM-4.7-Flash-64x2.6B-Q4_K_M`
- GRACI must never depend on the 4090 to complete required work.
- Before sending inference or other workloads to the 4090, GRACI must determine that `ModOrganizer.exe` is not running on the 4090 PC.
- If `ModOrganizer.exe` is running, GRACI must send no tasks to the 4090.
- Remote detection of `ModOrganizer.exe` is unresolved and must remain fail-closed. Until detection is implemented and verified, the 4090 is not eligible for GRACI workloads.
- Local AI is the default.
- Cloud AI is an exception and escalation path, not the normal execution path.
- No cloud-AI integration is authorized for Phase 1A.
- The repository and durable on-disk state are authoritative. Do not rely on conversation history as project state.

## Known blocker

The Work environment cannot currently authenticate a safe, read-only remote process query on the 4090 PC. A least-privilege mechanism must later be selected, authorized, implemented, and verified before the 4090 becomes workload-eligible.

## Next work

The next authorized phase is Phase 3 — Resource / Model Router. It must not treat
optional 4090 capacity as available while the process-detection blocker remains
unresolved. Phase 3 has not started.
