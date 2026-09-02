# GRACI known issues

> Classification: current issue and unresolved-evidence register
> Authority: descriptive Product Owner/runtime record; issue closure requires evidence
> Verified against: promoted Phase 8D commit `a0a61b7298d3c85cec054cd11ca827842f2776dd`
> Last verified: 2026-09-01

## GRACI-ISSUE-001 — Cold-start/runtime-readiness failure

**Status: CLOSED / REPAIRED / PRODUCT OWNER ACCEPTED**

The Product Owner observed a real cold-start failure:

1. Windows cold startup completed.
2. Major services appeared healthy.
3. The browser/runtime request path nevertheless failed.
4. Pressing **GRACI Restart** restored operation.

The defect was reproduced during the Product Owner-authorized Phase 8D controlled
cold-start procedure. Its technical repair and repeated automated procedure are
complete, and the Product Owner accepted Phase 8D on 2026-09-01.

Earlier supporting observation: on 2026-09-01 direct Windows enumeration confirmed
the exact root task `\GRACI Resident Host` installed, enabled, `Ready`, and reporting
last result `0`, but no resident process was active, port `127.0.0.1:8766` refused
connections, and a stale resident state record remained. The task launches a
short-lived PowerShell startup script; its successful result does not prove that the
spawned resident remained alive or that the browser/runtime path became and stayed
ready. This observation is not itself a root-cause determination and does not
invalidate the earlier Product Owner report.

Controlled evidence run `bc8f35d52b844889bf74eaa48927721f` followed a full
shutdown and new boot at `2026-09-02T02:28:25.5000000Z`. Through the sustained 60,
120, and 300 second checkpoints:

- the resident task reported result `0`;
- one owned resident process stayed alive;
- the resident health and browser endpoints remained responsive and fresh; and
- the lifecycle ledger retained launcher publication and heartbeats.

The required primary router failed separately. Its task reported result `1`, port
`127.0.0.1:8080` remained closed, and Phase 8D correctly reported overall runtime
`unavailable`. Windows Code Integrity events `3033` and `3077` recorded that
`llama-server.exe` attempted to load unsigned `llama-server-impl.dll`, which violated
the enforced `VerifiedAndReputableDesktop` policy
`{0283ac0f-fff1-49ae-ada1-8a933130cad6}`. A separate version-only probe reproduced
`0xC0E90002` (`STATUS_SYSTEM_INTEGRITY_POLICY_VIOLATION`). The controlled evidence is
summarized in [`ACC-0003`](acceptance/ACC-0003-phase8d-cold-start.md).

The Product Owner authorized a security-preserving repair. Official llama.cpp b9637
CUDA 13.3 archives matched the SHA-256 digests published by the upstream release.
The executable and sampled llama.cpp DLLs remain `NotSigned`, but the unchanged
active `VerifiedAndReputableDesktop` policy permitted the exact candidate. This is
live allowability evidence under the active verification/reputation enforcement,
not a code-signing claim. The candidate supported every pinned GRACI router flag and
passed an isolated router, two-model inventory, and OpenAI-compatible request smoke
test while spawning Qwen with the pinned `--n-gpu-layers all` setting. The production
`llama-server.exe` hash is
`06444801bb1dc38a848bb5a527728c4ea14ad2aa45ce7e81a29a5fb5d2560eaf`.
No Code Integrity, Smart App Control, signing, trust, or allowlist setting changed.

Repeat controlled run `1df4990ca2ed4dbb87f3f4478027fcf0` followed the new boot at
`2026-09-02T02:56:45.5000000Z`. At the sustained 60, 120, and 300 second checkpoints:

- both exact scheduled tasks were registered, enabled, `Ready`, and returned `0`
  after the new boot;
- one owned resident instance remained alive with no terminal lifecycle event;
- resident health was fresh and `ready`, and browser identity remained valid;
- the primary router responded with both approved models; and
- lifecycle heartbeats continued after the resident launcher exited.

The automated summary is `PASS`; the temporary collector task completed with result
`0` and was removed. The Product Owner subsequently accepted Phase 8D.

**Historical workaround:** the Product Owner previously observed **GRACI Restart**
recover operation. It was not reattempted after the enforced Code Integrity failure
and must not be credited as evidence for the subsequent repair or passing repeat.

**Closure evidence:** the repeated procedure now supplies the controlled startup
timeline that
distinguishes task missing, task access denied/unknown, task registered, launcher
succeeded, owned process alive, and runtime ready; actual service/process/endpoint
behavior rather than task registration or exit code alone; sustained resident and
browser readiness after the launcher exits; browser-path result before manual
restart; enough lifecycle evidence to determine a later resident exit when
reasonably possible; security-approved repair evidence; and a repeated passing
cold-start procedure. Explicit Product Owner acceptance completed closure.

**Phase 8D implementation note:** promoted commit `a0a61b7` provides the required
typed distinctions, actual resident endpoint probe, freshness/recovery state,
visualizer projection, trusted context, and bounded lifecycle ledger. This
instrumentation exposed and preserved the first failure and verified the repeated
repair outcome; it did not grant repair or acceptance authority.

## GRACI-ISSUE-002 — Startup status can misreport access denial as absence

**Status: REPAIRED IN CURRENT IMPLEMENTATION; RESTRICTED-CONTEXT LIVE ACCEPTANCE NOT RECORDED**

[`ops/status-graci-login-tasks.ps1`](../ops/status-graci-login-tasks.ps1) calls
`Get-ScheduledTask` with access errors suppressed and interprets a null result as
`not installed`. On 2026-09-01 this was reproduced from a restricted caller context:
both exact task lookups returned `Access denied`, while the script reported both as
not installed. Direct Windows enumeration then confirmed both tasks present at the
Task Scheduler root.

This was a diagnostic defect, not evidence of task-registration loss. The current
script uses exact root-path lookups with terminating errors and separately reports
`missing`, `access denied / unknown`, `registered`, and `launcher succeeded`.
Static regression tests cover the classification contract. Direct execution on
2026-09-01 correctly reported both exact tasks registered and launcher-succeeded;
the restricted-token error branch has not been physically re-run after repair.

## GRACI-GAP-001: Telemetry 1.0.1 acceptance

**Status: CLOSED / PRODUCT OWNER ACCEPTED**

Live 3090-side observation on 2026-09-01 confirmed schema 2, agent version 1.0.1,
fresh observations, RTX 4090 identity, and observed below-normal priority. The
separately authorized 2026-09-02 procedure then passed controlled boot-triggered
startup without a manual start, exact single-process/listener ownership,
below-normal priority, qualified memory/CPU/GPU/latency expectations, advancing
observations, unchanged MO2/router behavior, and automatic resident-HUD
reacquisition. See [`ACC-0006`](acceptance/ACC-0006-4090-telemetry.md).

The technical evidence gap is closed. On 2026-09-02, the Product Owner explicitly
accepted telemetry 1.0.1 on the bounded evidence in `ACC-0006`. The acceptance does
not grant workload, routing, or expanded remote-execution authority.

## GRACI-GAP-002 — Narrow physical QA scope remains unrecorded

The current UI baseline is physically accepted. Existing records do not establish
that every earlier manual scenario was included in that acceptance, including all
multi-tab/race, autoplay, reboot, and CLI physical microphone cases. Do not infer
failure; record explicit evidence if those scenarios become acceptance requirements.

## GRACI-GAP-003 — Optional 4090 llama.cpp upgrade

**Status: CLOSED / PRODUCT OWNER ACCEPTED**

Official b10675 is deployed at the existing pinned path. Both approved models passed
real inference from the 3090, the old b10516 directory remains recoverable, and an
actual rollback-to-old/readiness/re-promote/readiness cycle passed. MO2 remained
exactly `NOT_RUNNING`; the 4090 remains optional and the port-8080 firewall remains
restricted to the 3090. See [`ACC-0004`](acceptance/ACC-0004-4090-llama-upgrade.md).
Controlled restart validation passed with task, hash, firewall, MO2, telemetry, and
both model requests correct after the new boot. The Product Owner explicitly
accepted the upgrade and confirmed gaming-impact acceptance as verified on
2026-09-02.

## GRACI-GAP-004 — Non-interactive 4090 remoting credential lifecycle

**Status: CLOSED / PRODUCT OWNER ACCEPTED / ROTATION REQUIRED BEFORE EXPIRY**

One-way certificate-authenticated WinRM is deployed and passed positive identity,
elevation, file-transfer, unmapped-certificate rejection, and controlled-restart
tests. Routine sessions no longer require or store the account password. The
non-exportable client certificate expires on 2028-09-02; the status diagnostic
fails closed within a configurable minimum-validity window. Certificate rotation
must be completed before expiry. A future change of the 3090 Windows execution
identity requires explicit key reprovisioning because the private key is scoped to
the current user. Connectivity remains technical capability, not blanket authority.
See [`ACC-0005`](acceptance/ACC-0005-4090-certificate-remoting.md).
