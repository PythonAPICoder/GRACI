# GRACI operations

> Classification: current topology, procedures, and time-stamped operational evidence
> Authority: descriptive; live state must be rechecked before an operational action
> Verified at commit: `dbc27123e0ab25a22ac1128677d2cd385de7d662`
> Last verified: 2026-09-01

## Stable topology

| Component | Location | Contract |
|---|---|---|
| Authoritative repository | RTX 3090 host, `E:\GRACI` | Canonical source, documentation, local run records, and governed memory |
| Primary model router | `http://127.0.0.1:8080/v1` | Local llama.cpp router; Qwen and GLM allowlist; 3090 remains sufficient |
| Resident visualizer/operator | `http://127.0.0.1:8766/` | Loopback-only observer plus explicit bounded PTT, Restart, and speech claim/lifecycle controls |
| Optional 4090 model router | `http://192.168.0.101:8080/v1` | Optional capacity only; never a baseline dependency |
| Optional 4090 MO2 status | `http://192.168.0.101:8765/graci/v1/mo2` | Exact read-only `ModOrganizer.exe` state used by fail-closed eligibility policy |
| Optional 4090 telemetry | `http://192.168.0.101:8767` | Fixed read-only `/health` and `/telemetry`; presentation only |

Shared storage exists between the machines as optional infrastructure. It is not
authoritative GRACI storage and must not become a dependency without a clear,
separately reviewed benefit. The repository on the 3090 remains authoritative.

## Startup ownership

The 3090 uses separate current-user, limited, at-logon scheduled tasks:

- `\GRACI 3090 llama.cpp Router`
- `\GRACI Resident Host`

Scripts under [`ops/`](../ops/) install, start, stop, remove, and report these named
resources using GRACI-specific state and identity validation. Do not substitute broad
process matching or force-kill unrelated processes.

Direct Windows Task Scheduler enumeration on 2026-09-01 confirmed both exact root
tasks installed, enabled, and `Ready`, with last task result `0`. Their actions,
working directory, current-user interactive logon trigger, and limited principal
matched the repository installers.

For the resident, scheduled-task success proves only that the PowerShell launcher
started a matching resident and then completed successfully. The launcher exits
after startup; Task Scheduler does not thereby prove or supervise continued
resident-process liveness, visualizer endpoint availability, or browser/runtime
readiness. Registration, launcher result, owned-process liveness, and runtime
readiness are separate facts.

The current [`status-graci-login-tasks.ps1`](../ops/status-graci-login-tasks.ps1)
suppresses `Get-ScheduledTask` access errors. In a restricted caller context this can
return null and incorrectly print `not installed` when the actual state is `access
denied / unknown`. Until repaired, do not treat that message as proof of absence
unless task enumeration access was established.

Useful read-only checks are:

```powershell
.\ops\status-graci-login-tasks.ps1
Invoke-RestMethod http://127.0.0.1:8080/v1/models
Invoke-RestMethod http://192.168.0.101:8765/graci/v1/mo2
Invoke-RestMethod http://192.168.0.101:8767/health
Invoke-RestMethod http://192.168.0.101:8767/telemetry
```

## Operational snapshot — 2026-09-01

- Both 3090 scheduled tasks were installed, enabled, `Ready`, and reported last task
  result `0`. A later direct reconciliation confirmed the exact root paths
  `\GRACI 3090 llama.cpp Router` and `\GRACI Resident Host`; an intervening
  `not installed` report was a restricted-access false negative.
- The 3090 router was healthy; Qwen was loaded and GLM available/unloaded.
- The resident was not active and `127.0.0.1:8766` refused connections despite a
  resident state file. This is recorded with the open cold-start/readiness issue and
  must not be generalized into expected architecture.
- The optional 4090 model router exposed both approved models, unloaded at the
  observation time.
- The MO2 service reported exact process absent / `NOT_RUNNING`.
- Telemetry `/health` and `/telemetry` were live with schema 2, agent 1.0.1, fresh
  observations, RTX 4090 identity, and below-normal effective priority.

These are time-stamped observations, not guarantees of later state.

## Telemetry deployment versus acceptance

Telemetry agent 1.0.1 deployment is confirmed. Full reboot/startup, sustained
resource, duplicate-process, gaming-impact, and Product Owner acceptance remain
unestablished. The reviewed deployment/update/rollback and separate reboot procedure
remain in [`telemetry_agent/README.md`](../telemetry_agent/README.md).
