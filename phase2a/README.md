# GRACI Phase 2A single-agent autonomous repair loop

Phase 2A was accepted on 2026-08-27 (America/Chicago) from Phase 1 baseline
`fa425eaeebe262e401ace78163497f331d07d4a4`.

`graci.autonomous.AutonomousRepairController` is a bounded state machine for an
existing disposable, non-Git workspace. The caller supplies exact readable and
editable file allowlists plus a test directory. Each model response is one strict
JSON decision: `inspect_file`, `write_text`, `run_tests`, or `finish`. Exact schema
validation and independent workspace/allowlist policy validation occur before every
tool invocation. The model cannot provide commands, endpoints, models, permissions,
budgets, or verification settings.

Defaults are 8 total cycles, 2 repair writes, and a 30-second command timeout. A
failed test is retained as bounded feedback for a later cycle. Test output and file
content sent back to the model are capped at 12,000 characters per field and only
the last three completed cycles are included. Full cycle evidence is atomically
persisted. Exhausted budgets, malformed/unsupported decisions, policy violations,
provider failures, non-test tool failures, `finish` without passing tests, and
inconsistent test evidence all terminate as FAIL.

Final PASS requires a governed `run_tests` result whose command completed without a
timeout, reports success, and has exit code 0. Model claims never establish PASS.

## Verification

- `python -W error -m unittest discover -s tests -v`: 43 tests passed, including all
  32 Phase 1 regression tests.
- The deterministic multi-attempt case performed an ineffective first replacement,
  captured failing unittest output, supplied that evidence to the next decision,
  performed a second governed replacement, and passed the rerun.
- `python -m compileall -q graci tests phase2a`, `git diff --check`, and the complete
  diff/security review passed.

## Live validation

Run `2dede672-a6cf-4285-9b9f-505cb296fce6` used only provider
`local-llama-cpp`, node `3090-primary-localhost`, endpoint
`http://127.0.0.1:8080/v1`, and server-reported model
`qwen3.8-27b-q4_k_m`. GRACI created no production-repository repair target: the
runner made a temporary fixture, and Qwen used governed actions to inspect its source
and test, atomically repair the allowlisted source, and request the fixed unittest
suite. The test process exited 0 and deterministic verification set PASS. The
temporary fixture was then deleted automatically.

Evidence is `evidence/2dede672-a6cf-4285-9b9f-505cb296fce6.json`. Reproduce with
`python -m phase2a.run_live_validation` from the repository root.

The first live request returned Markdown-fenced JSON and was rejected before tool
execution. The provider instruction was clarified; strict parsing was not weakened.

## Safety and limitations

Traversal, absolute outside paths, symlink escapes, sensitive names, `.git`, and
non-allowlisted files remain prohibited. Commands remain fixed argument arrays with
no shell. There is no package installation, network tool, Git mutation, system
configuration, cloud path, or 4090 path. The fixed Config continues to reject all
other endpoints and models. Phase 2A uses full-file replacement and caller-defined
file scope; it has no reviewer, multi-model adjudication, routing, scheduling,
memory, or open-ended planning. Phase 2B is the next authorized stage.
