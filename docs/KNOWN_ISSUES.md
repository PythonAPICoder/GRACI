# GRACI known issues

> Classification: current issue and unresolved-evidence register
> Authority: descriptive Product Owner/runtime record; issue closure requires evidence
> Verified against: promoted Phase 8D commit `a0a61b7298d3c85cec054cd11ca827842f2776dd`
> Last verified: 2026-09-01

## GRACI-ISSUE-001 — Cold-start/runtime-readiness failure

**Status: OPEN / REPRODUCED / ROOT CAUSE IDENTIFIED**

The Product Owner observed a real cold-start failure:

1. Windows cold startup completed.
2. Major services appeared healthy.
3. The browser/runtime request path nevertheless failed.
4. Pressing **GRACI Restart** restored operation.

The defect was reproduced during the Product Owner-authorized Phase 8D controlled
cold-start procedure. It remains open pending a security-approved repair, a passing
repeat procedure, and explicit Product Owner disposition.

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

**Historical workaround:** the Product Owner previously observed **GRACI Restart**
recover operation. It was not reattempted after the enforced Code Integrity failure
and must not be assumed effective against the current blocker.

**Closure evidence required:** controlled startup/reboot procedure; a timeline that
distinguishes task missing, task access denied/unknown, task registered, launcher
succeeded, owned process alive, and runtime ready; actual service/process/endpoint
behavior rather than task registration or exit code alone; sustained resident and
browser readiness after the launcher exits; browser-path result before manual
restart; enough lifecycle evidence to determine a later resident exit when
reasonably possible; security-approved repair evidence; regression coverage where
feasible; a repeated passing cold-start procedure; and explicit Product Owner
disposition.

**Phase 8D implementation note:** promoted commit `a0a61b7` provides the required
typed distinctions, actual resident endpoint probe, freshness/recovery state,
visualizer projection, trusted context, and bounded lifecycle ledger. This
instrumentation exposed and preserved the failure but does not repair or close it.
No Code Integrity, Smart App Control, signing, trust, or allowlist setting was
changed. Selecting a trusted/signed/reputable llama.cpp artifact or an explicitly
reviewed signing/trust path is a Product Owner security decision.

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

## GRACI-GAP-001 — Telemetry 1.0.1 acceptance incomplete

**Status: DEPLOYED; ACCEPTANCE INCOMPLETE**

Live 3090-side observation on 2026-09-01 confirmed schema 2, agent version 1.0.1,
fresh observations, RTX 4090 identity, and observed below-normal priority. This
confirms deployment, not the separately documented reboot-startup, sustained
resource, duplicate-process, gaming-impact, or full Product Owner acceptance
procedure.

## GRACI-GAP-002 — Narrow physical QA scope remains unrecorded

The current UI baseline is physically accepted. Existing records do not establish
that every earlier manual scenario was included in that acceptance, including all
multi-tab/race, autoplay, reboot, and CLI physical microphone cases. Do not infer
failure; record explicit evidence if those scenarios become acceptance requirements.
