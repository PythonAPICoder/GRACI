# GRACI Phase 1C first vertical slice

Phase 1C was verified on 2026-08-27 (America/Chicago).

`graci.vertical_slice.VerticalSliceController` accepts a task, an existing isolated
workspace, and one explicitly allowed relative target. It reuses the Phase 1A fixed
localhost provider and Phase 1B `ToolLayer`. A Git repository root cannot be used as
the live workspace, and `.git` paths are prohibited. The model contract contains exactly
`schema_version`, `action`, `target_path`, `content`, and `rationale`; the sole
supported action is `write_text`.

GRACI checks the response model identity, strict schema, workspace containment,
sensitive-path policy, and exact configured target before execution. It then uses
the controlled atomic text tool and independently reads the result. Only exact
content equality establishes `PASS`; model wording or claims never establish
success. Each run is atomically persisted with task, provider identity, proposed
action, validation, tool result, verification, status, errors, and UTC timestamps.

Verification evidence:

- `python -W error -m unittest discover -s tests -v`: 26 tests passed.
- Tests cover valid, malformed, and unsupported actions; traversal/outside and
  sensitive paths; successful modification; verification success and failure; tool
  failure; truthful PASS/FAIL; complete evidence; and a model success claim unable
  to override failed deterministic verification.
- Live run `626af57f-f32a-4563-8af1-7f2a7b02b019` returned HTTP 200 from
  `http://127.0.0.1:8080/v1`, with server-reported model
  `qwen3.8-27b-q4_k_m`. It proposed the configured `result.txt`, passed schema and
  policy validation, wrote 43 bytes through `ToolLayer`, and passed exact read-back
  verification. The record is under `evidence/` and resulting file under
  `live-sandbox/`.
- No 4090 workload, cloud AI, package installation, arbitrary shell command, Git
  mutation by the model, secret storage, or system configuration change occurred.

Current limitations: one synchronous single-file task per run; no planning,
multi-step operation, retry/repair, reviewer, routing, scheduling, cloud escalation,
memory, service/API wrapper, or automatic workspace creation. Parent directories
must already exist. The unresolved 4090 process-detection blocker remains closed.
