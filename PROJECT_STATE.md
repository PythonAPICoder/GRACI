# GRACI Project State

This document and the durable files in this repository are the authoritative source of GRACI project state. Conversation history is not project state.

## Project and phase

GRACI is a local-first AI workload orchestration project. It will coordinate inference resources while preserving safe availability rules and the ability to operate entirely on the primary host.

Current phase: **Phase 1A complete**. The minimal production local controller is implemented and verified. The next authorized phase is **Phase 1B**, but it has not begun.

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
- There are no retries, reviewers, resource scheduling, cloud escalation, authentication, service/API wrapper, or 4090 execution path.
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

## Next authorized work

Phase 1B may begin only in a separate authorized work session. Do not treat optional 4090 capacity as available while the process-detection blocker remains unresolved.
