# GRACI Project State

This document and the durable files in this repository are the authoritative source of GRACI project state. Conversation history is not project state.

## Project and phase

GRACI is a local-first AI workload orchestration project. It will coordinate inference resources while preserving safe availability rules and the ability to operate entirely on the primary host.

Current phase: **Gate 0 qualified baseline**. No production implementation has started. The next authorized phase is **Phase 1A**; its implementation must begin in a new Work session.

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

Begin Phase 1A in a new Work session, using this document and the Gate 0 evidence as the starting state. Do not treat optional 4090 capacity as available while the process-detection blocker remains unresolved.
