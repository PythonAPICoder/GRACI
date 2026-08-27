# GRACI Phase 2 acceptance and closure

Phase 2C was accepted on 2026-08-27 (America/Chicago) from the committed Phase 2B
baseline `eb2e03e89cb6228b3291c5fc58b20e7b7392296c`. The accepted closure commit is
the commit named `Complete GRACI Phase 2 acceptance` that contains this record.

## Integrated deterministic acceptance

`tests/test_phase2c_acceptance.py` challenges the complete loop rather than merely
rerunning earlier unit cases. Together with the retained Phase 1, 2A, and 2B tests,
it proves direct inspection/write/test success; multi-file inspection and two
independently governed writes; failed tests, bounded feedback, repair, and retest;
repair, iteration, model-call, inspection, and modification limits; malformed JSON;
policy rejection before outside mutation; independent validation of every action;
repeat, no-change retest, and premature-finish guards; provider and governed test
failures; deterministic rejection of model false-success; and ordered reconstructable
PASS/FAIL evidence.

The warning-strict command `python -W error -m unittest discover -s tests -v`
passed all 58 tests. `python -m compileall -q graci tests phase1a phase1b phase1c
phase1d phase2a phase2b phase2c`, JSON parsing of all accepted evidence files, secret
pattern review, evidence consistency review, and `git diff --check` passed.

## Live acceptance

Run `218d2969-cd66-44b2-bab0-073abecdf975` used only provider
`local-llama-cpp`, node `3090-primary-localhost`, endpoint
`http://127.0.0.1:8080/v1`, and server-reported model
`qwen3.8-27b-q4_k_m`. GRACI operated on an automatically removed disposable
non-Git fixture whose pricing implementation and related configuration both had
defects. Across seven cycles, Qwen listed the bounded scope, inspected `policy.py`,
`pricing.py`, and `tests/test_pricing.py`, independently replaced both editable
files, and requested the fixed warning-strict unittest command. Both deterministic
tests passed with exit code 0; only that evidence established PASS.

The full durable record is
`evidence/218d2969-cd66-44b2-bab0-073abecdf975.json`. Reproduce from the repository
root with `python -m phase2c.run_live_acceptance`.

## Safety and evidence audits

The review confirmed workspace containment, traversal and absolute-outside
rejection, symlink resolution, sensitive-name and `.git` blocking, caller-defined
read/write allowlists, non-Git autonomous workspaces, atomic whole-file replacement,
fixed unittest execution with `shell=False`, command allowlisting, read-only Git
observation, local endpoint/model configuration, bounded context, hard budgets,
timeouts, progress guards, and deterministic PASS authority. There is no arbitrary
shell, Git mutation, package installation, external network tool, system configuration
tool, policy/budget mutation by the model, cloud path, or 4090 path.

All representative Phase 2A, Phase 2B, and new Phase 2C records parse as JSON and
contain task/run identity, UTC timestamps, endpoint/model, configured and consumed
budgets, ordered decisions and validations, tool/test outcomes, feedback, repairs,
guard events where applicable, deterministic verification, terminal reason, status,
and errors. No credential or secret material was found.

Two genuine defects were repaired. Repair exhaustion after a failed test had used
the total write count, so legitimate multi-file setup writes could consume the
documented post-failure repair allowance; enforcement now uses only the repair
budget. Unexpected governed execution exceptions already failed closed but could
leave `terminal_reason` null; they now persist `execution_failure`. Both have
regression coverage.

## Limitations and closure

Phase 2 remains synchronous and single-model. The caller must create the disposable
workspace and enumerate readable/editable files and the test directory. Changes are
complete-file replacements, and tests are limited to the fixed unittest command.
There is no reviewer, adjudication, semantic memory, dynamic planning/tool discovery,
service wrapper, routing, scheduling, Git mutation, arbitrary shell, package/network
operation, 4090 use, or cloud escalation. The unresolved safe 4090 process-detection
requirement remains fail-closed.

Phase 2 is complete. Phase 3 — Resource / Model Router is the next authorized phase;
it has not begun.
