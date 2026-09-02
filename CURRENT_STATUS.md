# Current GRACI status

> Classification: current implementation, deployment, acceptance, and issue status
> Authority: descriptive; canonical policy remains under `governance/`
> Verified against: promoted Phase 8D commit `a0a61b7298d3c85cec054cd11ca827842f2776dd`
> Last verified: 2026-09-02

## Product and repository baseline

- Local `main` and `origin/main` are at accepted 4090 upgrade and certificate-remoting
  commit `e412d1c18a2726edda2838362807428b7f7d17ee`; promoted Phase 8D implementation
  commit `a0a61b7298d3c85cec054cd11ca827842f2776dd` is in that history.
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

Telemetry 1.0.1 deployment remains confirmed. On 2026-09-02, a separately authorized
telemetry-validation procedure using certificate remoting also established
boot-triggered startup without a manual start, one fixed process and listener,
below-normal priority, qualified memory/CPU/GPU/latency behavior, advancing real
observations, unchanged MO2/router behavior, and automatic 3090 resident-HUD
reacquisition. The technical result is **PASS**, and the Product Owner accepted
telemetry 1.0.1 on 2026-09-02. See
[`ACC-0006`](docs/acceptance/ACC-0006-4090-telemetry.md).

A restricted-access follow-up incorrectly reported both 3090 tasks as not installed.
Direct Windows enumeration proved that report false: the status script had suppressed
`Get-ScheduledTask` access-denied errors and converted null results to `not installed`.
The current task-registration state remains confirmed; task result `0` does not prove
continued resident liveness or browser/runtime readiness after its launcher exits.

## Reliability and acceptance items

- **Cold-start/runtime-readiness defect: CLOSED / REPAIRED / PRODUCT OWNER
  ACCEPTED.** The first controlled run reproduced an unavailable
  required runtime because Code Integrity blocked llama.cpp b10516. The authorized
  repair deployed official-release b9637 without changing the enforced
  `VerifiedAndReputableDesktop` policy. Repeat run
  `1df4990ca2ed4dbb87f3f4478027fcf0` passed launcher, process, browser, endpoint,
  model, and heartbeat checks through five minutes. The Product Owner accepted Phase
  8D on 2026-09-01. See `GRACI-ISSUE-001` and `ACC-0003`.
- **Startup-status diagnostic defect: REPAIRED IN CURRENT IMPLEMENTATION.** Restricted
  task-enumeration access can no longer be collapsed into task absence. The repair
  is test-verified and direct normal-context execution is verified; a restricted-token
  live acceptance check remains optional evidence. See `GRACI-ISSUE-002`.
- Telemetry 1.0.1 controlled reboot, single-instance/resource behavior, and HUD
  reacquisition passed; the Product Owner accepted the bounded capability.
- The optional 4090 now runs official llama.cpp b10675. Live Qwen/GLM inference and
  an exercised b10516 rollback/re-promotion cycle passed. A controlled restart also
  passed; the Product Owner accepted the upgrade and verified gaming impact.
- One-way certificate-authenticated HTTPS WinRM from the 3090 to the 4090 is
  deployed. Passwordless command execution, file transfer, rejection of an unmapped
  certificate, and reconnect after a controlled restart passed. The Product Owner
  accepted the capability.
- The accepted UI baseline does not by itself prove every earlier manual multi-tab,
  autoplay, race, reboot, or CLI microphone scenario.

See [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md).

## Current development state

The durable repository-memory/documentation foundation passed a fresh-session
reconstruction test and is **PRODUCT OWNER ACCEPTED**. Its temporary bootstrap
migration package has been removed.

Phase 8D System Health & Trusted Runtime Context is **PROMOTED AND DEPLOYED AT
`a0a61b7`**. It adds typed component and
startup-stage observations, freshness/recovery reduction, actual loopback runtime
probing, trusted local time/context injection, visualizer health projection, repaired
startup diagnostics, and a bounded resident lifecycle ledger.

Verification evidence: the canonical warning-strict suite passed all 567 tests on
2026-09-01, focused Phase 8D/startup/resident suites passed, PowerShell diagnostic
scripts parsed successfully, documentation links resolved, and `git diff --check`
passed. Test-created synthetic `runs/` records were identified against a pre-test
snapshot and removed; pre-existing run records were preserved.

After promotion, the resident was launched and reached sustained `ready` state. The
first separately authorized full shutdown/cold-start run kept the resident/browser
ready but exposed `STATUS_SYSTEM_INTEGRITY_POLICY_VIOLATION` in the required b10516
3090 router. The Product Owner then authorized a security-preserving repair. The
official b9637 CUDA 13.3 release archives matched their published SHA-256 digests;
the candidate supported all pinned router flags, passed the unchanged active Code
Integrity policy, and completed an isolated CUDA-build router/model request using
the pinned `--n-gpu-layers all` setting before deployment.
The blocked b10516 directory remains preserved at
`E:\llama.cpp\bin-b10516-ci-blocked-20260902` for recovery.

Repeat evidence run `1df4990ca2ed4dbb87f3f4478027fcf0` followed a full shutdown
and new boot at `2026-09-02T02:56:45.5000000Z`. Both scheduled launchers returned
`0`; one owned resident instance, browser/health path, primary router/model inventory,
and lifecycle heartbeats remained valid at 60, 120, and 300 seconds. The automated
summary is `PASS`, the temporary collector task was removed, and live Phase 8D
readiness was `ready` afterward. The durable record is
[`ACC-0003-phase8d-cold-start.md`](docs/acceptance/ACC-0003-phase8d-cold-start.md).

Phase 8D is **PROMOTED, DEPLOYED, AUTOMATED COLD-START VALIDATED, AND PRODUCT OWNER
ACCEPTED**. The separate bounded 4090 llama.cpp inspection, upgrade, deployment,
rollback verification, and live acceptance procedure is complete at the machine
level: official b10675 is deployed, both approved models returned `READY`, and the
old build was restored successfully before final re-promotion. A new boot preserved
the task, hash, firewall, MO2/telemetry readiness, and both model responses. Product
Owner acceptance is recorded for both the upgrade and one-way certificate remoting;
no later development objective is authorized.

The future product direction is selective governed composition: use routing, review,
memory, optional compute, recovery, and verification when the task, policy, latency,
resources, and verification need warrant them—not on every turn by default.

Current authorization and sequencing are maintained in
[`docs/ROADMAP.md`](docs/ROADMAP.md). Historical phase closure and evidence remain
indexed by [`docs/history/PHASE_INDEX.md`](docs/history/PHASE_INDEX.md); historical
“next phase” statements and old test counts are not current status.
