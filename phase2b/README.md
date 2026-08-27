# GRACI Phase 2B governed multi-step autonomy

Phase 2B extends the Phase 2A state machine; it does not introduce an unrestricted
agent. One local-model decision is accepted per cycle and must match one exact
contract: `list_files`, `inspect_file`, `write_text`, `run_tests`, or `finish`.
Schema, action, workspace, policy, and budget validation are recorded independently
before execution. All file reads and replacements remain confined to caller-defined
allowlists in an existing disposable non-Git workspace. Test execution remains the
fixed warning-strict unittest command; there is no model-supplied command text.

The default hard limits are 12 iterations, 12 model calls, 6 file inspections, 4
file modifications, 2 post-failure repairs, a 30-second test timeout, 12,000
model-visible characters per evidence field, 6 recent cycles, and 2 identical
actions before the next repetition is rejected. Records contain consumed and
remaining budgets. Repeated identical actions, retesting a known failure without a
change, and premature `finish` decisions fail closed. Truncation is deterministic
and recorded; complete tool results remain in atomic durable evidence.

Final PASS can only follow a consistent governed test record with command success,
exit code 0, no timeout, and PASS status. Model wording cannot establish success.

## Verification

- `python -W error -m unittest discover -s tests -v`: 50 tests passed, including
  all Phase 1 and Phase 2A regressions.
- Deterministic Phase 2B tests cover two-file/two-modification success, failed-test
  feedback and later repair, valid-first/invalid-second action rejection, every new
  budget, repeat guards, context truncation, evidence ordering, and deterministic
  authority.
- Compilation and `git diff --check` passed.

## Live validation

Run `cf3c6de8-1bf7-404b-8ff2-c521d6d0776a` used only `local-llama-cpp` at
`http://127.0.0.1:8080/v1`, with server-reported model
`qwen3.8-27b-q4_k_m`. Across 7 cycles Qwen listed the allowlist, inspected three
files, independently replaced `settings.py` and `invoice.py`, and requested tests.
Both deterministic tests passed. The disposable fixture was automatically deleted;
the ordered record is under `evidence/`. Reproduce with
`python -m phase2b.run_live_validation`.

## Safety and limitations

Path containment, traversal/absolute-outside rejection, sensitive and `.git` path
blocking, exact read/write allowlists, fixed commands, atomic writes, local-only
provider/model configuration, and Git-root rejection are unchanged. There is no
arbitrary shell, Git mutation, package/network/system tool, cloud path, or 4090 path.
The loop remains synchronous, uses whole-file replacement, has no independent
reviewer, routing, scheduling, memory, or semantic planning, and requires the caller
to enumerate file scope and the test directory.
