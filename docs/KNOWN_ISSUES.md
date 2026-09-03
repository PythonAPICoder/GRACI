# GRACI known issues

> Classification: current issue and unresolved-evidence register
> Authority: descriptive Product Owner/runtime record; issue closure requires evidence
> Verified through: PO-DEC-040
> Last verified: 2026-09-03

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

## GRACI-ISSUE-003: Phase 8E Stage 2 AppLocker architecture caused host outage

**State: OPERATIONALLY REMEDIATED; FUNCTIONAL WITH HARMLESS RESIDUE**

Phase 8E Stage 2 enabled machine-wide AppLocker EXE enforcement without a Packaged
App collection. Windows consequently blocked packaged applications under Event
8027, including Codex and Snipping Tool. Recovery required removal of the GRACI
policy and later offline cache removal followed by reboot.

PO-DEC-039 rejects the AppLocker architecture as unsafe and disproportionate. It is
not part of the current baseline. The repository entry points are quarantined, and
a narrower identity, filesystem, inert-content, manifest, immutable-generation,
constrained-viewer, and validated-launcher architecture is approved for design only.

The separately authorized Gate 1, Gate 2, and post-reboot Gate 3 all passed on
2026-09-03. The final evidence showed empty local and effective policy, an empty
`SrpV2` root, no enforcing collection, normal classic and packaged application
execution, and no post-boot AppLocker warning, error, deny, Event 8026, or Event
8027. The Product Owner classified the host as `FUNCTIONAL WITH HARMLESS RESIDUE`
and marked the incident operationally remediated. The empty-policy, service, driver,
and cache residue is not approved for cleanup.

The unsafe Stage 2 path remains rejected, superseded, and quarantined. Replacement
Phase 8E implementation and later Phase 8F work remain separate future work and are
not authorized. See
[`INC-0001`](incidents/INC-0001-phase8e-stage2-applocker.md),
[`ACC-0012`](acceptance/ACC-0012-phase8e-incident-response.md), the
[`operational closure`](acceptance/ACC-0013-phase8e-applocker-operational-closure.md), the
[`replacement design`](PHASE_8E_REPLACEMENT_BOUNDARY_DESIGN.md), and the
[`executed audit plan`](PHASE_8E_READ_ONLY_HOST_AUDIT_PLAN.md).

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

## GRACI-GAP-005: Phase 8E projection at-rest protection

**Status: CLOSED / PRODUCT OWNER ACCEPTED RISK**

The authorized Stage 2 inspection found that NTFS `E:` has no associated BitLocker
volume. The Product Owner confirmed that both systems are physically controlled in
the home and explicitly accepted the unencrypted-storage risk. BitLocker must not
be installed, enabled, configured, or deployed on any drive, folder, or file on
either system.

This closes BitLocker as a Phase 8E prerequisite. The BitLocker decision does not
authorize real governed memory, a real-data projection, Stage 3, or Stage 4. The
Product Owner separately accepted Stage 2 on 2026-09-02. See
[`ACC-0008`](acceptance/ACC-0008-phase8e-stage2-windows.md) and `PO-DEC-029`.

## GRACI-GAP-006: existing per-user Obsidian candidate does not run under review identity

**Status: CLOSED BY DEDICATED COPY / ORIGINAL CANDIDATE FAILED CLOSED**

The exact signed per-user Obsidian 1.13.4 executable was temporarily granted
read-and-execute access to the dedicated review SID and protected by a firewall
block scoped to that SID. The review token read the executable and synthetic
projection, projection writes remained denied, and no non-loopback established
connection was observed. Obsidian did not remain running or register the synthetic
vault. Local AppLocker, Code Integrity, application-crash, and Windows Error
Reporting logs identified no policy or crash cause.

Rollback restored the original folder permissions, removed the temporary firewall
rule and review-profile state, and left that candidate unchanged and unqualified.

The Product Owner then authorized a separate copy under the review profile. The
exact copied 1.13.4 executable started under the real review token, registered the
synthetic vault, read all 25 notes, left the protected projection unchanged, and
was contained by its viewer-only outbound block. The Product Owner account retained
read access. The Product Owner historically accepted Stage 3, and routine launcher
promotion passed under the real review token. PO-DEC-039 later withdrew routine
launch because it depended on the rejected Stage 2 boundary. Real data, replacement
deployment, and automatic refresh remain unauthorized. See
[`ACC-0009`](acceptance/ACC-0009-phase8e-stage3-obsidian.md).

## GRACI-GAP-007: personalized learning is not connected to Obsidian or ordinary runtime

**Status: OPEN / SYNTHETIC FOUNDATION ACCEPTED / NOT DEPLOYED**

The accepted synthetic Obsidian viewer does not yet fulfill the Product Owner's
central goal for the vault. G.R.A.C.I. cannot yet capture an approved preference,
working method, taught or learned task procedure, correction, or lesson through an
ordinary conversation, retrieve it automatically during later relevant work, or
publish it into the readable vault.

Closure requires a bounded design for proposing and approving durable memories,
ordinary source-traceable retrieval, correction and deletion, taught-task safety,
and maintainer-only vault refresh. The design must keep displayed notes from
granting authority and must preserve explicit approval for new or changed durable
knowledge. `PO-DEC-034` establishes the outcome, and `PO-DEC-035` authorizes the
separate synthetic-only design and implementation task. Real personal data,
deployment, and automatic updates remain unauthorized.

The accepted foundation implements the bounded synthetic lifecycle and
manual projection adapter described in
[`PERSONALIZED_MEMORY_FOUNDATION.md`](PERSONALIZED_MEMORY_FOUNDATION.md). Focused
tests cover no-write-without-approval, exact approval, scope, provenance,
correction, retirement, conflict, stale state, injection isolation, failed-write
preservation, audited rollback, and deterministic projection. The Product Owner
accepted the synthetic foundation under PO-DEC-036 and authorized its commit and
push. The gap remains open because no trusted ordinary-turn adapter, real-data
boundary, runtime retrieval, maintainer command, or real vault refresh exists.

## GRACI-GAP-008: Phase 8F broker is synthetic and lacks production trust anchors

**Status: OPEN / STAGE 1 PRODUCT OWNER ACCEPTED / PRODUCTION WORK UNAUTHORIZED**

PO-DEC-037 authorized an isolated synthetic-only trusted secret broker foundation,
and PO-DEC-038 accepts that foundation for repository preservation. The
implementation can test exact capability grants, encrypted custody, opaque
references, one fixed adapter operation, persistent reservation, replay control,
audit, recovery, and rollback without exposing a general raw-secret interface.

It is not a production credential capability. Closure for any real use requires
separate Product Owner scope for a production caller identity, protected durable key
custody, Windows account and ACL design, live local IPC authentication, backup and
restore, an external anti-rollback anchor, in-flight revocation policy, connector
qualification, real-data handling, deployment, ordinary runtime integration, and
acceptance. PO-DEC-038 authorizes none of those actions and explicitly prohibits
beginning later Phase 8F work by implication.
