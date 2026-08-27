# GRACI Phase 2 Autonomous Loop

Phase 1 is complete, and Phase 2B provides a bounded governed multi-step repair loop
over a disposable workspace. Local Qwen can list configured scope, inspect explicitly
allowlisted files, make multiple independently governed replacements, and request the
fixed deterministic unittest command. Only verified tests establish PASS.

Submit a task with Python 3.14 or later:

```powershell
python -m graci "Return PASS with a short confirmation that this task completed."
```

The controller uses only `http://127.0.0.1:8080/v1` and model
`qwen3.8-27b-q4_k_m`. It prints the complete run record and exits zero only for a
strictly validated model `PASS`. Every execution writes `runs/<run-id>.json`.

Run the complete warning-strict offline and acceptance suite with:

```powershell
python -W error -m unittest discover -s tests -v
```

All inference is fixed to local provider `local-llama-cpp`, endpoint
`http://127.0.0.1:8080/v1`, and model `qwen3.8-27b-q4_k_m`. The unresolved safe
process-detection requirement keeps the 4090 unavailable, and Phase 1 has no cloud
AI path.

Phase 1B adds a deterministic, workspace-contained `graci.ToolLayer` for safe text
file operations, a narrow approved command policy, unittest execution, and read-only
Git observation. It is a programmatic interface only; models do not autonomously
invoke tools in this phase. See `phase1b/README.md` for its security boundary and
verification record.

Phase 1C integrates the local provider and controlled tool layer for one bounded
text-file action. The workspace must already exist and the only permitted target is
configured by the caller:

```powershell
python -m graci --workspace .\isolated-sandbox --target result.txt "Create result.txt containing exactly: example"
```

The model may propose only the strict `write_text` action contract. GRACI validates
the schema and exact target, executes through `ToolLayer`, reads the file back, and
reports `PASS` only when the observed content exactly equals the proposed content.
See `phase1c/README.md` for the accepted live evidence and limitations.

Phase 1D adds deterministic integrated acceptance cases for valid execution,
malformed output, policy rejection, verification mismatch, tool failure, and
evidence integrity. Its closure record and live evidence are under `phase1d/`.

Phase 2A is available programmatically as `AutonomousRepairController`; its accepted
localhost integration runner is `python -m phase2a.run_live_validation`. The default
loop limits are 8 cycles, 2 repair writes, and a 30-second test timeout. See
`phase2a/README.md` for the contract, safety boundary, tests, and live evidence.

Phase 2B extends that same explicit state machine with independent iteration, model
call, inspection, modification, repair, timeout, and context budgets plus simple
repeat guards. Its accepted multi-file live runner is
`python -m phase2b.run_live_validation`; see `phase2b/README.md`.

The implementation still has no reviewer model, unrestricted planning,
scheduling, routing, memory, arbitrary shell, package/network operations, Git
mutation, 4090 execution, or cloud escalation. Phase 2C is next and has not begun.
