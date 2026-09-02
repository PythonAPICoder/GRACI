# GRACI known issues

> Classification: current issue and unresolved-evidence register
> Authority: descriptive Product Owner/runtime record; issue closure requires evidence
> Verified at commit: `dbc27123e0ab25a22ac1128677d2cd385de7d662`
> Last verified: 2026-09-01

## GRACI-ISSUE-001 — Cold-start/runtime-readiness failure

**Status: OPEN**

The Product Owner observed a real cold-start failure:

1. Windows cold startup completed.
2. Major services appeared healthy.
3. The browser/runtime request path nevertheless failed.
4. Pressing **GRACI Restart** restored operation.

The defect is not closed merely because it was not reproduced during the memory
audit. It remains open until a deliberate cold-start test either reproduces and
repairs it or establishes, with evidence and Product Owner review, that it is
resolved.

Current supporting observation: on 2026-09-01 direct Windows enumeration confirmed
the exact root task `\GRACI Resident Host` installed, enabled, `Ready`, and reporting
last result `0`, but no resident process was active, port `127.0.0.1:8766` refused
connections, and a stale resident state record remained. The task launches a
short-lived PowerShell startup script; its successful result does not prove that the
spawned resident remained alive or that the browser/runtime path became and stayed
ready. This observation is not itself a root-cause determination and does not
invalidate the earlier Product Owner report.

**Workaround:** the Product Owner-observed workaround is **GRACI Restart**.

**Closure evidence required:** controlled startup/reboot procedure; a timeline that
distinguishes task missing, task access denied/unknown, task registered, launcher
succeeded, owned process alive, and runtime ready; actual service/process/endpoint
behavior rather than task registration or exit code alone; sustained resident and
browser readiness after the launcher exits; browser-path result before manual
restart; enough lifecycle evidence to determine a later resident exit when
reasonably possible; repair evidence if reproduced; regression coverage where
feasible; and explicit Product Owner disposition.

## GRACI-ISSUE-002 — Startup status can misreport access denial as absence

**Status: OPEN**

[`ops/status-graci-login-tasks.ps1`](../ops/status-graci-login-tasks.ps1) calls
`Get-ScheduledTask` with access errors suppressed and interprets a null result as
`not installed`. On 2026-09-01 this was reproduced from a restricted caller context:
both exact task lookups returned `Access denied`, while the script reported both as
not installed. Direct Windows enumeration then confirmed both tasks present at the
Task Scheduler root.

This is a diagnostic defect, not evidence of task-registration loss. Until repaired,
the script's `not installed` result is authoritative only when enumeration access is
known to have succeeded. Phase 8D planning must distinguish missing from access
denied/unknown and preserve the evidence behind that classification.

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
