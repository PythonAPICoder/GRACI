# GRACI Phase 4B Governed Memory Pipeline

Phases 0–3 and Phase 4A remain complete. Phase 4B adds explicit provenance-forcing
write capabilities, operation-level retry idempotency, and bounded deterministic
exact retrieval over the local Phase 4A JSON store. Memory remains inert untrusted
context and grants no execution, policy, routing, or acceptance authority. There is
no automatic conversation memory, semantic search, prompt injection, network/cloud,
4090, shared-drive, or Obsidian dependency. Architecture and accepted synthetic live
evidence are under `phase4b/`. The next authorized stage is Phase 4C — Relevance,
Scope & Supersession; it has not begun.

# GRACI Phase 4A Persistent Memory Storage

Phases 0–3 remain complete. Phase 4A adds a local-only, versioned, strict JSON
memory-record schema and atomic filesystem store. Memory is untrusted contextual
data and cannot override user instructions, policy, evidence, or verified state.
Storage is authoritative on the 3090, has no cloud/4090/Obsidian dependency, and
does not implement automatic writes, semantic retrieval, or prompt injection.
Architecture and acceptance details are in `phase4a/README.md`. The next authorized
stage is Phase 4B — Memory Write / Retrieval Pipeline; it has not begun.

# GRACI Phase 3 Resource / Model Router — Phase 3 Complete

Phase 1 and Phase 2 are complete. Phase 3A added the deterministic typed resource,
endpoint, model, health, and eligibility registry. Phase 3B uses it to route the
implementer role to Qwen and reviewer/verifier roles to GLM on the primary 3090.
Phase 3C evaluates whether the optional 4090 is eligible using exact MO2 process
state plus independent endpoint/model health. Phase 3D may place an explicitly
optional workload there only after a fresh eligible result, with bounded 3090 fallback.
Phase 3E integrated acceptance is complete. The next authorized phase is Phase 4 —
Persistent Memory; it has not begun.
Phase 2 provides a bounded governed multi-step repair loop
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

All inference uses local provider `local-llama-cpp`. The authoritative default is
`http://127.0.0.1:8080/v1`; explicit optional-capacity requests may use the eligible
4090 at `http://192.168.0.101:8080/v1`. Governed implementation uses
`qwen3.8-27b-q4_k_m`; required read-only review uses
`GLM-4.7-Flash-64x2.6B-Q4_K_M`. The accepted system has no cloud AI path.

Phase 3 closure details and durable evidence are under `phase3e/`. The complete
warning-strict suite passes 107 tests. The 3090 remains independently sufficient;
the 4090 is optional, requires `prefer_optional=True`, and is freshly fail-closed
against exact `ModOrganizer.exe` state, endpoint health, model presence, and
non-future evidence no older than 10 seconds.

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

Phase 2C closes Phase 2 with integrated deterministic acceptance of success,
repair/retest, hard-budget, malformed-response, policy, progress-guard, provider,
tool, false-success, and evidence paths. The complete warning-strict suite has 58
tests. Its accepted localhost live runner is `python -m phase2c.run_live_acceptance`;
see `phase2c/README.md` and `phase2c/evidence/`.

See `phase3a/README.md` and `phase3a/evidence/` for the registered topology,
fail-closed health and eligibility semantics, and localhost-only validation.

Phase 3B adds `Phase3BRoleRouter` and `Phase3BController`. After deterministic test
success, GLM receives only bounded allowlisted evidence and returns a strict review
contract. Ordinary code adjudicates tests plus review; reviewer FAIL, malformed
output, identity mismatch, or provider failure prevents workflow PASS. See
`phase3b/README.md` and `phase3b/evidence/`.

Phase 3C adds the fixed read-only `ModOrganizer.exe` status detector and pure 4090
eligibility policy. Both real MO2 states were observed: NOT_RUNNING plus healthy
models was eligible, while RUNNING plus the same healthy endpoint was ineligible
with `mo2_running`. See `phase3c/README.md` and `phase3c/evidence/`.

Phase 3D adds explicit deterministic optional placement. Every new remote dispatch
uses fresh Phase 3C observations no more than 10 seconds old. An ineligible gate
causes zero 4090 inference; a failed remote attempt is recorded and followed by at
most one 3090 attempt. Live acceptance proved eligible 4090 inference and MO2-running
3090 fallback. See `phase3d/README.md` and `phase3d/evidence/`.

The implementation still has no reviewer-driven repair, reviewer tools,
unrestricted planning, scheduling, load balancing, memory, arbitrary shell,
package installation, Git mutation by models, remote administration, opaque load
balancing, shared mutable coordination, or cloud escalation. Phase 3E — Resource /
Model Router Acceptance & Closure is the next authorized stage.
