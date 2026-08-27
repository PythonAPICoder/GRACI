# GRACI Phase 1D acceptance and closure

Phase 1D was accepted on 2026-08-27 (America/Chicago) from committed Phase 1C
baseline `8d4eec707fd76db391168dbc91e47720d4eafbdf`.

## Deterministic acceptance scenarios

`tests/test_phase1_acceptance.py` integrates the controller contract, provider
response boundary, action validation and policy, controlled tool layer,
deterministic verification, and durable evidence persistence. It proves:

- a valid structured action performs the controlled write and returns PASS only
  after exact read-back;
- malformed/schema-invalid output is rejected without tool mutation;
- traversal outside the workspace is rejected before mutation;
- injected observed-state mismatch returns FAIL despite model success wording;
- an injected controlled-tool failure propagates as FAIL without mutation; and
- successful and failed records contain task, run ID, UTC timestamps, fixed
  provider/endpoint/model identity, proposed action when parseable, validation,
  tool and verification results, final status, and errors.

The complete command `python -W error -m unittest discover -s tests -v` passed all
32 tests. `python -m compileall -q graci tests` and `git diff --check` also passed.

## Live acceptance

Run `315228d2-3413-4a8b-b059-2c3efc727ac7` used only
`http://127.0.0.1:8080/v1`, provider `local-llama-cpp`, node
`3090-primary-localhost`, and server-reported model `qwen3.8-27b-q4_k_m`. Local
Qwen proposed the configured `phase1-accepted.txt` action. Schema and policy
validation passed, `ToolLayer` atomically wrote 38 UTF-8 bytes, and independent
read-back exactly matched the proposed content. Deterministic verification therefore
set final status PASS.

The durable record is
`evidence/315228d2-3413-4a8b-b059-2c3efc727ac7.json`; the verified artifact is
`live-sandbox/phase1-accepted.txt`. The reproducible live runner is invoked from the
repository root as `python -m phase1d.run_live_acceptance`.

## Safety review and limitations

Workspace containment, traversal and symlink escape handling, sensitive-path and
`.git` protection, exact-target enforcement, command allowlisting, Git read-only
policy, and absence of package/network/system mutation tools remain intact. The
review found one defect: configuration allowed arbitrary non-empty model names.
`Config` now permits only `qwen3.8-27b-q4_k_m`, and the acceptance suite covers
rejection of alternate local models, the 4090 endpoint/node, and cloud endpoints.

No 4090 workload, cloud AI, external network access, dependency installation,
secret storage, or system configuration change occurred. The initial direct-script
live-run invocation failed locally before inference because the repository package
was not on that invocation's import path; the documented module invocation then
completed successfully. No disposable artifact resulted.

Phase 1 is limited to one synchronous bounded text-file action with exact content
verification. There is no autonomous or multi-step loop, repair/retry, reviewer,
routing, scheduling, memory, service/API wrapper, arbitrary shell, Git mutation,
package management, network tool, 4090 execution, or cloud escalation. Phase 2 —
Autonomous Loop is the next authorized phase and has not started.
