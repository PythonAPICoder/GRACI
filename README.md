# GRACI Phase 8 — Presence & Visual Identity In Progress

**G.R.A.C.I.** = **General Reasoning And Conversational Intelligence**

This is the current product-owner canonical identity definition. It supersedes the
former expansion without rewriting historical project records.

## Explicit PTT speech barge-in

While GRACI is in `SPEAKING`, a new explicit browser pointer/Spacebar hold or CLI
Spacebar hold stops only GRACI's owned local playback process and begins `LISTENING`.
The previous governed result and its `AuthoritativeFinalResponse` are already complete
and remain unchanged. The new press never submits work; release still finalizes one
deferred-STT transcript and is the only boundary that may start exactly one new
governed turn. Cancelled, blank, failed, interrupted, or timed-out capture submits
nothing. Ordinary PTT, browser focus-loss safety, streaming STT, Kokoro `af_heart`
speed `1.00`, and `GRAY-see` pronunciation are unchanged.

## Windows resident host

GRACI has one supported always-available composition for the authoritative 3090 PC.
The resident host owns one existing governed runtime composition and the local
visualizer at `http://127.0.0.1:8766/`. It publishes `IDLE` at startup
and then waits. **Resident does not mean autonomous:** startup submits no task, starts
no run, performs no follow-up, and activates no microphone. The microphone remains
inactive unless an operator explicitly holds the browser PTT control (or valid
Spacebar shortcut) or starts the existing CLI push-to-talk path. The browser exposes
only this narrow explicit voice turn; it has no generic task-submission authority.
A successful browser voice turn displays the validated response and, by default,
presents that same `AuthoritativeFinalResponse` through the existing Phase 6D local
Kokoro `af_heart` and Windows playback path. Typed interactions retain their existing
explicit `--speak` behavior.

Run operator scripts from the repository root. Where local PowerShell policy blocks
scripts, use process-only bypass (it does not change machine or user policy):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\start-graci-resident.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\status-graci-resident.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\stop-graci-resident.ps1
```

The start command is idempotent. A GRACI-specific OS lock is the authoritative
single-instance boundary; state records are instance-specific and the scripts also
validate the OS lock, PID, executable, module record, and instance ID. Stop is cooperative
and never kills a Python process. While resident ownership is active, the one-shot
CLI fails closed rather than constructing a competing runtime. Stop the resident to
use the otherwise unchanged one-shot CLI.

On Windows, the scripts select exactly one registered Python 3.14+ executable and
fail closed if none or more than one is eligible. An operator may instead provide one
absolute existing executable with `-Python C:\path\to\python.exe`; the scheduled-task
installer resolves and records that concrete path rather than relying on task PATH.

Automatic start is an explicit current-user Task Scheduler action:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\install-graci-resident-task.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\remove-graci-resident-task.ps1
```

The task runs at interactive logon with limited privilege, an unlimited resident
execution duration, bounded restart settings, and `MultipleInstances=IgnoreNew`.
The in-process lock remains the safety boundary if Task Scheduler or a manual start
races. Installation/removal changes only the named `GRACI Resident Host` task and is
never implicit. Removal does not stop an already-running host; use the stop command
separately. No scheduled task is installed by repository setup or tests.

## Authoritative 3090 llama.cpp router and login startup

The accepted local Qwen/GLM workflow uses llama.cpp's native router mode; it does not
keep both 16.8/18.1 GB GGUFs resident on the 24 GB RTX 3090. Its lifecycle commands are:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\start-3090-llama-router.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\status-3090-llama-router.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\stop-3090-llama-router.ps1
```

The script refuses to run while port 8080 is occupied. Stop the existing server by
its original operator mechanism first; do not kill it by name. The script validates
the exact two GGUF files, starts `E:\llama.cpp\bin\llama-server.exe` bound only to
loopback with `--models-dir E:\llama.cpp\models --models-max 1 --models-autoload`,
uses a bounded 32,768-token context and one slot for VRAM reliability, and waits up
to 30 seconds for both approved IDs to appear. Startup lists the models but does not
request `/models/load`; the existing governed model lease remains solely responsible
for Qwen/GLM demand switching.

Install or remove its distinct current-user logon task explicitly with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\install-3090-llama-router-task.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\remove-3090-llama-router-task.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\status-graci-login-tasks.ps1
```

`GRACI 3090 llama.cpp Router` and `GRACI Resident Host` are separate limited,
interactive-logon tasks with `IgnoreNew`, bounded restart settings, hidden
noninteractive PowerShell launchers, hidden child processes, and redirected logs.
The separation means router failure never kills the observer-only resident. Task
startup is not backend health authority; model calls retain existing fail-closed
health and lease checks. Install/remove affect only their exact GRACI task names.

The router start uses a GRACI startup mutex and validated ownership record, refuses
an occupied port, recovers stale state, and never replaces another process. Stop
validates the recorded PID executable before stopping that exact router; it never
uses broad process-name matching. For manual acceptance, request
Qwen, confirm its `/v1/models` status is `loaded`, run one harmless completion, then
repeat for GLM and finally Qwen. Each request must use the exact registered model ID.
Do not contact `192.168.0.101`; required reviewer work is 3090-only.

**Phase 8A — COMPLETE. Phase 8 — IN PROGRESS.** Trusted observer state now drives
a bounded presentation-only GRACI presence. The resident visualizer has one narrow
explicit PTT operator path; every other panel remains observer-only. Voice lifecycle
is observed, the 3090 remains independently sufficient, and optional 4090/MO2 policy
is unchanged. Later Phase 8 work remains
unauthorized. Details and evidence are under `phase8a/`.

# GRACI Phase 7 — Bounded Explicit Local Interaction Complete

**Phase 7 — COMPLETE AT BOUNDED EXPLICIT LOCAL INTERACTION.** Ordinary local typed
input and explicit one-turn push-to-talk share the Phase 7A coordinator and exactly
one governed `run(task)` boundary. Accepted input submits once; rejected or failed
input submits zero times. Optional `--speak` and observer-only lifecycle publication
cannot replace governed truth. Phase 1C workspace/target remains a distinct specialized
legacy mode. The 3090 remains independently sufficient and the 4090 remains optional
under unchanged MO2 policy. Broader interaction and Phase 8 work require separate
authorization. See `phase7/` and `phase7c/`.

# GRACI Phase 7B Local Operator CLI Integration — Complete

Ordinary `python -m graci "task"` interaction now uses the accepted Phase 7A
single-turn coordinator. `python -m graci --speech` performs at most one explicit
push-to-talk turn: hold Spacebar to capture, then release Spacebar to stop and
transcribe. Key repeat does not restart capture and no Enter press is required.
Add `--speak` only when local Kokoro `af_heart` presentation is desired. There is no
implicit microphone or speaker use, retry, wake word, always-listening behavior,
automatic follow-up, REPL, or conversation loop. Output is bounded JSON and
presentation cannot alter governed authority. Phase 7C later accepted this bounded
composition and closed Phase 7. Details and evidence are under `phase7b/`.

Add `--visualizer` to an ordinary typed or explicit speech turn to serve the same
in-process observer stream at `http://127.0.0.1:8766/`. For a one-shot turn that a
human needs time to inspect, also add `--visualizer-hold`; GRACI waits for Enter after
the turn and then stops the server. That one-shot visualizer remains observer-only.
The resident visualizer adds explicit browser PTT; neither surface has routing,
shutdown, memory, model, or generic mutation controls.

# GRACI Phase 7A Explicit Turn Coordinator — Complete

Phase 7 has begun. Phase 7A adds a production coordinator for one explicitly
initiated typed or push-to-talk turn. Both sources enter the same existing governed
`run(task)` boundary, with at most one submission per turn. The frozen turn result
keeps governed authority independent from explicitly constructed final-response text
and optional accepted local speech presentation. There is no autonomous conversation
loop, wake word, always-listening mode, new persistence, or new routing authority.
The 3090 remains sufficient and the 4090 remains optional under existing MO2 policy.
Details and evidence are under `phase7a/`; Phase 7C later accepted this coordinator
without authorizing broader interaction behavior.

# GRACI Phase 6 Integrated Voice Acceptance — Complete

Phase 6 is complete at bounded push-to-talk voice interaction: explicit local capture,
local STT, typed-input-equivalent governed submission, optional bounded local speech
presentation from an explicit authoritative final response, and observer-only
`IDLE`/`LISTENING`/`SPEAKING`. Integrated deterministic acceptance adds no production
coordinator or autonomous voice loop. Closure evidence is under `phase6/`. No Phase
6F is named or authorized; future voice enhancements require separate authorization.

# GRACI Phase 6E Voice Lifecycle Publication — Complete

Phase 6E reuses the canonical observer state model to publish `LISTENING` only during
bounded Phase 6B microphone capture and `SPEAKING` only during actual Phase 6D
playback. Guarded leases deterministically restore `IDLE`; publisher failures are
recorded and isolated from transcription, presentation, and governed runtime results.
Architecture, deterministic tests, and closure evidence are under `phase6e/`.

# GRACI Phase 6D Local TTS and Bounded Audio Playback — Complete

Phase 6D adds an optional presentation-only path from an explicitly constructed
authoritative final user-facing response through local Kokoro-82M ONNX CPU synthesis
with the current `af_heart` production selection at speed `1.00` and bounded
subprocess-isolated Windows playback. Speech failure does not alter the governed task
result. Phase 6A pronunciation overrides are applied only to the speech copy.
Architecture, reconstruction, tests, and evidence are under `phase6d/`. Phase 6E
later added observer-only lifecycle publication without changing
this accepted presentation boundary.

# GRACI Phase 5C Command-Center UI

Phase 5C adds the packaged observer-only browser command center at `http://127.0.0.1:8766/`. It is an offline HTML/CSS/vanilla-JavaScript/SVG interface over the accepted Phase 5A contract and Phase 5B read-only backend. Design, operation, security, and acceptance details are under `phase5c/`.

# GRACI Phase 5B Local Visualizer Backend

Phase 5B adds an optional standard-library, observer-only HTTP/SSE transport for the
accepted Phase 5A immutable projection. It binds only `127.0.0.1:8766`, exposes four
versioned read endpoints, retains 100 recent events, and permits at most eight live
SSE clients. It has no control, provider, tool, memory-write, routing, MO2 mutation,
remote, filesystem, cloud, or inference path. Architecture and acceptance details
are under `phase5b/`.

# GRACI Phase 5A Visualizer State Contract — Complete

Phase 5A defines versioned immutable snapshot and event contracts plus a pure,
observer-only projector over trusted runtime facts. It exposes bounded task,
3090/4090, MO2, Qwen/GLM, memory metadata, tool/test, review/adjudication, and recent
event state without adding authority. The event buffer retains at most 100 entries;
display text is hard-bounded; prompts, memory contents, raw output, secrets, and
hidden reasoning are excluded by architecture. Offline lifecycle acceptance and
details are under `phase5a/`. Phase 5A includes no UI, server, controls, voice, or
remote access. The next authorized stage is Phase 5B — Local Visualizer Backend; it
has not begun.

# GRACI Phase 4 Persistent Memory — Complete

Phase 4E integrated acceptance is complete. The local 3090-authoritative persistent
memory subsystem now has accepted canonical JSON storage, governed writes and exact
retrieval, explicit relevance/scope/lifecycle governance, and bounded untrusted-data
integration with Qwen. Memory grants no authority, GLM remains content-independent,
and the 4090, shared drive, Obsidian, and cloud are not canonical-memory dependencies.
Closure architecture and evidence are under `phase4e/`. The next authorized phase is
Phase 5 — Visualizer; it has not begun.

# GRACI Phase 4D Memory-Guided Agent Execution

Phases 0–3 and Phase 4A–4C remain complete. Phase 4D supplies exact governed
memory selection to local Qwen through a bounded structured untrusted-data envelope.
Optional and required modes are caller-controlled; selected/supplied IDs and safe
exclusions are auditable. Existing tools, tests, budgets, routing, MO2, reviewer,
and adjudication remain authoritative. GLM receives usage metadata, not memory
content. There is no automatic memory write, semantic search, cloud memory, shared
mutable 4090 vault, or 4090 dependency. Architecture and evidence are under
`phase4d/`. The next authorized stage is Phase 4E — Persistent Memory Acceptance &
Closure; it has not begun.

# GRACI Phase 4C Governed Memory Selection

Phases 0–3 and Phase 4A/4B remain complete. Phase 4C adds exact relevance keys,
explicit project/session identity and scope composition, historical supersession,
trusted-clock expiration, ambiguity exclusion, and bounded deterministic selection.
Memory remains inert context and grants no authority. There is no semantic search,
embedding, model conflict resolution, prompt injection, autonomous memory use,
cloud memory, or 4090 dependency. Architecture and evidence are under `phase4c/`.
The next authorized stage is Phase 4D — Memory-Guided Agent Execution; it has not
begun.

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
# GRACI Phase 8 — Presence & Visual Identity In Progress

**Phase 8A — COMPLETE. Phase 8 — IN PROGRESS.** The existing Phase 5 read-only
visualizer now maps trusted `system_state` facts to a bounded, presentation-only
GRACI presence. The authoritative state label, stale/disconnected truth, operational
panels, and MO2-blocked optional 4090 status remain visible. Voice lifecycle is
observed, never controlled. The 3090 remains independently sufficient, the 4090 and
MO2 policy are unchanged, and later Phase 8 refinement remains unauthorized. See
`phase8a/` for the contract and closure evidence.
