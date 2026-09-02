# Current GRACI status

> Classification: current implementation, deployment, acceptance, and issue status
> Authority: descriptive; canonical policy remains under `governance/`
> Verified through: PO-DEC-036 on 2026-09-02
> Last verified: 2026-09-02

## Product and repository baseline

- Accepted Phase 8E Stage 1 implementation commit
  `023a5ff9c78b549ac9d5d80ac3a3f1b92048ca12` was fast-forwarded to local `main`
  and `origin/main` on 2026-09-02. It was built from development-process commit
  `08b2ffd`; promoted Phase 8D commit `a0a61b7` remains in its history.
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

The Product Owner accepted the Phase 8E read-only review design and its fixture-only
Stage 1 implementation. The separate `phase8e` package now implements
the typed source catalog, exact local Git-commit projection, exact-ID synthetic
memory privacy modes, deterministic active-content neutralization, complete source
and output hashing, immutable generation promotion, source-race checks, and tamper
verification. Focused tests pass. Ordinary GRACI runtime does not import the
exporter. Stage 1 is not deployed and has not used real data. The Product Owner
authorized and accepted Stage 2 local Windows viewer-boundary implementation and
synthetic verification. Stage 3 is now accepted, and its dedicated Obsidian copy and
routine fail-closed launcher are locally deployed. Real memory, real-data generation,
automatic refresh, runtime integration, and later work remain unauthorized.

The authorized Stage 2 technical procedure is now implemented and locally applied.
Actual viewer-token tests passed source and staging denial, projection read-only
behavior, executable and script denial, tamper detection, failed-refresh
preservation, resident independence, rollback, and reapply. The final synthetic
generation is `8e000002-0000-4000-8000-000000002001`. The `E:` volume is not
BitLocker-protected. The Product Owner accepted that physical-security risk and
directed that BitLocker remain uninstalled and unconfigured on both systems. Real
or sensitive projection data remains separately unauthorized. The Product Owner
accepted Stage 2 and authorized its commit and push to `main` on 2026-09-02.
Obsidian is already installed but, according to the Product Owner, has never been
used. Stage 2 did not inspect, open, configure, or qualify it. See
[`ACC-0008`](docs/acceptance/ACC-0008-phase8e-stage2-windows.md).

The Product Owner then authorized a narrow Stage 3 candidate test using that exact
Obsidian executable, a review-SID-only outbound firewall block, and synthetic data.
The review token could read the program and synthetic projection but could not
change the projection. Obsidian did not remain running or register the synthetic
vault, so the candidate failed qualification. Rollback restored the original
Obsidian-folder permissions, removed the temporary firewall rule and review-profile
state, and left the Product Owner's installation unchanged. Stage 2 and the resident
GRACI page remained healthy. A separate review-account installation or further
diagnosis required separate authorization. See
[`Stage 3 test evidence`](phase8e/evidence/stage3-obsidian-test-20260902.json).

The Product Owner then authorized a separate local copy for `GRACI_Review` while
preserving the Product Owner account's vault access. The exact verified application
tree was copied into the review profile. Under the real review token, Obsidian
started, registered `E:\GRACI-Review-Projection`, read all 25 synthetic notes, and
could not change the immutable generation. The exact viewer-only firewall rule
blocked its update checks. A JSON encoding warning was corrected, and the complete
retest passed without a configuration parse error. The Product Owner account read
all 25 notes and the vault configuration; its existing Obsidian executable and
settings remained unchanged. Stage 2 verification passed and the resident page
returned HTTP 200. The Product Owner accepted Stage 3 and authorized routine launch,
commit, and push. Promotion passed under the actual review token, the exact launcher
and qualification record are deployed, no non-loopback connection was observed, and
the resident page remained HTTP 200. Real data and automatic refresh remain
unauthorized. The Product Owner subsequently directed that G.R.A.C.I. should
learn and later reuse approved personal preferences, working methods, taught task
procedures, corrections, and lessons, with Obsidian serving as their readable view.
Adding or changing a memory requires explicit current verbal or PTT approval. That
direction is recorded in `PO-DEC-034`; no real personalized-memory capture,
retrieval, or vault-maintenance integration is implemented or authorized. See
[`ACC-0009`](docs/acceptance/ACC-0009-phase8e-stage3-obsidian.md).

The separate PO-DEC-035 task produced a synthetic-only implementation foundation.
It adds exact proposal digests, typed-turn and PTT approval attestations,
schema-v3 approval provenance, immutable state and audit generations, scoped
retrieval, correction, retirement, conflict and stale-state handling, hash-bound
rollback, and an exact-generation Phase 8E projection adapter. The Product Owner
accepted the synthetic foundation under PO-DEC-036 and authorized its commit and
push. It remains outside ordinary runtime composition, has used no real personal
data, and is not deployed or automatically refreshed. See
[`ACC-0010`](docs/acceptance/ACC-0010-phase8e-personalized-memory.md) and
[`PERSONALIZED_MEMORY_FOUNDATION.md`](docs/PERSONALIZED_MEMORY_FOUNDATION.md).

The durable repository-memory/documentation foundation passed a fresh-session
reconstruction test and is **PRODUCT OWNER ACCEPTED**. Its temporary bootstrap
migration package has been removed.

Phase 8D System Health & Trusted Runtime Context is **PROMOTED AND DEPLOYED AT
`a0a61b7`**. It adds typed component and
startup-stage observations, freshness/recovery reduction, actual loopback runtime
probing, trusted local time/context injection, visualizer health projection, repaired
startup diagnostics, and a bounded resident lifecycle ledger.

The 4090 status-answer correction is deployed in the running resident. It labels
Qwen and GLM load state as primary 3090 facts, reports each model's 4090 endpoint
availability separately, and states the MO2 rule explicitly: MO2 absent permits
optional AI use when the other checks pass, while MO2 running blocks it. The full
warning-strict suite passed all 610 tests during the authorized stop/test/restart
procedure. The restarted resident reached ready state, and its live snapshot showed
both 4090 models available, MO2 `NOT_RUNNING`, and eligibility `true`.

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
Owner acceptance is recorded for both the upgrade and one-way certificate remoting.
Phase 8E Stages 1 through 3 are Product Owner accepted. Stage 4 and all later Phase
8E work remain unauthorized.

The future product direction is selective governed composition: use routing, review,
memory, optional compute, recovery, and verification when the task, policy, latency,
resources, and verification need warrant them—not on every turn by default.

Current authorization and sequencing are maintained in
[`docs/ROADMAP.md`](docs/ROADMAP.md). Historical phase closure and evidence remain
indexed by [`docs/history/PHASE_INDEX.md`](docs/history/PHASE_INDEX.md); historical
“next phase” statements and old test counts are not current status.
