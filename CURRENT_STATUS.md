# Current GRACI status

> Classification: current implementation, deployment, acceptance, and issue status
> Authority: descriptive; canonical policy remains under `governance/`
> Verified against: Phase 8D implementation worktree based on `959347207ecbfa252ca801ca85b76d355fc4dde2`
> Last verified: 2026-09-01

## Product and repository baseline

- Branch/commit verified before Phase 8D changes: local `main` and `origin/main` at
  `959347207ecbfa252ca801ca85b76d355fc4dde2`.
- Canonical identity: **G.R.A.C.I. = General Reasoning And Conversational
  Intelligence**.
- **Autonomous Assistant** is an approved subtitle/tagline, not acronym text.
- Production voice: local Kokoro `af_heart`, speed `1.00`, `GRACI -> GRAY-see`.
- The Product Owner physically accepts the current UI baseline at `dbc2712`:
  continuous voice-reactive outer ring, current subtitle, Data Chatter Thinking
  Pulse, symmetric HUD, and current voice/presence presentation.
- Earlier 64-bar/right-status-rail presentation is superseded current product design
  and remains historical only.

The acceptance scope is recorded in
[`docs/acceptance/ACC-0001-phase8-ui-baseline.md`](docs/acceptance/ACC-0001-phase8-ui-baseline.md).

## Implemented current capabilities

- Strict local Qwen conversational controller with bounded corrective validation
  retry and authoritative user-response separation.
- Explicit typed and PTT turn coordination, local CPU STT, local speech synthesis,
  browser-owned single-claim playback, and explicit barge-in.
- Loopback observer visualizer, trusted lifecycle projection, resident latest-turn
  continuity, symmetric hardware telemetry presentation, Data Chatter processing
  presence, and continuous speech-energy ring.
- Separate resident and 3090 llama.cpp-router startup ownership.
- Specialized bounded autonomous repair, Qwen/GLM routing/review, optional 4090
  routing/failover, and governed persistent-memory subsystems.

Ordinary CLI/resident turns currently use the plain Qwen `Controller`. They do not
automatically compose GLM review, governed memory, autonomous repair, or optional
4090 routing. See [`docs/CAPABILITY_MATRIX.md`](docs/CAPABILITY_MATRIX.md).

## Deployment observations — 2026-09-01

- `\GRACI 3090 llama.cpp Router` and `\GRACI Resident Host` scheduled tasks were
  directly confirmed at the Task Scheduler root, enabled, `Ready`, and reporting
  last result `0`.
- The 3090 router endpoint was healthy. Qwen was loaded; GLM was available and
  unloaded at observation time.
- The resident process was not active; `127.0.0.1:8766` refused connections and a
  stale resident state record existed. This is an observation, not an accepted steady
  state.
- The optional 4090 model endpoint exposed both approved models, unloaded at the
  observation time.
- Exact MO2 status reported `NOT_RUNNING`.
- Telemetry schema 2 agent version 1.0.1 was live with fresh RTX 4090/CPU/RAM data and
  observed below-normal priority.

Therefore telemetry 1.0.1 **is deployed and deployment is confirmed**. Full
reboot-startup, resource-impact, duplicate-process, gaming-impact, and Product Owner
acceptance are **not established**. Deployment and acceptance must remain separate.

A restricted-access follow-up incorrectly reported both 3090 tasks as not installed.
Direct Windows enumeration proved that report false: the status script had suppressed
`Get-ScheduledTask` access-denied errors and converted null results to `not installed`.
The current task-registration state remains confirmed; task result `0` does not prove
continued resident liveness or browser/runtime readiness after its launcher exits.

## Open reliability and acceptance items

- **Cold-start/runtime-readiness defect: OPEN.** The Product Owner observed a failed
  browser/runtime path after Windows cold startup that GRACI Restart recovered. It
  remains open until deliberately reproduced/repaired or proven resolved with
  evidence and Product Owner review.
- **Startup-status diagnostic defect: REPAIRED IN CURRENT IMPLEMENTATION.** Restricted
  task-enumeration access can no longer be collapsed into task absence. The repair
  is test-verified and direct normal-context execution is verified; a restricted-token
  live acceptance check remains optional evidence. See `GRACI-ISSUE-002`.
- Telemetry 1.0.1 full reboot/resource/Product Owner acceptance is incomplete.
- The accepted UI baseline does not by itself prove every earlier manual multi-tab,
  autoplay, race, reboot, or CLI microphone scenario.

See [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md).

## Current development state

The durable repository-memory/documentation foundation passed a fresh-session
reconstruction test and is **PRODUCT OWNER ACCEPTED**. Its temporary bootstrap
migration package has been removed.

Phase 8D System Health & Trusted Runtime Context is **IMPLEMENTED AND
DETERMINISTICALLY VERIFIED IN THE CURRENT WORKTREE**. It adds typed component and
startup-stage observations, freshness/recovery reduction, actual loopback runtime
probing, trusted local time/context injection, visualizer health projection, repaired
startup diagnostics, and a bounded resident lifecycle ledger. No service was
installed, started, stopped, restarted, deployed, or reboot-tested during
implementation.

Verification evidence: the canonical warning-strict suite passed all 567 tests on
2026-09-01, focused Phase 8D/startup/resident suites passed, PowerShell diagnostic
scripts parsed successfully, documentation links resolved, and `git diff --check`
passed. Test-created synthetic `runs/` records were identified against a pre-test
snapshot and removed; pre-existing run records were preserved.

Phase 8D is **NOT DEPLOYED, PROMOTED, OR PRODUCT OWNER ACCEPTED**. The current live
resident remains absent with stale state, while the router is healthy. Controlled
cold-start/reboot evidence and explicit Product Owner disposition remain required;
no later development objective is authorized.

The future product direction is selective governed composition: use routing, review,
memory, optional compute, recovery, and verification when the task, policy, latency,
resources, and verification need warrant them—not on every turn by default.

Current authorization and sequencing are maintained in
[`docs/ROADMAP.md`](docs/ROADMAP.md). Historical phase closure and evidence remain
indexed by [`docs/history/PHASE_INDEX.md`](docs/history/PHASE_INDEX.md); historical
“next phase” statements and old test counts are not current status.
