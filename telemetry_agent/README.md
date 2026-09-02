# GRACI 4090 read-only telemetry agent

> Classification: current component contract and operator procedure
> Verified source commit: `dbc27123e0ab25a22ac1128677d2cd385de7d662`
> Deployment observation: 2026-09-01

This standalone Windows package exposes cached presentation telemetry from the
optional 4090 node. It does not expose a shell, command execution, filesystem,
process, model, configuration, generic RPC, or write endpoint. It cannot make the
4090 eligible and does not modify the existing MO2/llama policy endpoint.

## Current deployment and acceptance status

Telemetry agent **1.0.1 deployment is confirmed**. The separately authorized
2026-09-02 controlled procedure passed boot-triggered startup without a manual
start, exact single-process/listener ownership, sustained resource expectations,
fresh observations, and automatic 3090 resident-HUD reacquisition. The durable
evidence is [`ACC-0006`](../docs/acceptance/ACC-0006-4090-telemetry.md).

The technical result is **PASS**. On 2026-09-02, the Product Owner explicitly
accepted telemetry 1.0.1 on the bounded `ACC-0006` evidence. That acceptance does
not grant workload, routing, or expanded remote-execution authority.

## Fixed production contract

- Python standard library only; no pip dependencies.
- Direct, persistent NVML access for exact GPU identity, utilization, VRAM bytes,
  and GPU temperature. It never polls `nvidia-smi`.
- Native `GetSystemTimes` and `GlobalMemoryStatusEx` for CPU utilization and RAM.
  CPU temperature is `null` / `not observed` because Windows has no safe,
  dependency-free sensor API for it.
- Sampling every 3 seconds into a bounded cache. Requests never sample hardware.
- Below-normal process priority is requested once at startup and then read back
  through `GetPriorityClass`. Schema 2 reports the request, application result,
  and observed effective priority separately. Correctness does not rely on
  priority. No CPU affinity or hard-coded CPU IDs are used.
- `GET http://192.168.0.101:8767/health`
- `GET http://192.168.0.101:8767/telemetry`
- Schema version 2, fixed object keys, maximum 16 KiB response. The 3090 client
  accepts the previously deployed schema 1 during the explicit rolling update.
- Application allowlist: 3090 `192.168.0.100`, local node, and loopback.
- Firewall allow rule: private network, TCP 8767, local `192.168.0.101`, remote
  `192.168.0.100`, and the selected Python executable only.

`config.defaults.json` is an operator-review manifest of these compiled, fixed
production values; it is not a remotely editable configuration channel. Tests keep
the manifest and implementation constants in lockstep.

The telemetry document has exact top-level keys: `schema_version`, `node_id`,
`hostname`, `observed_at_utc`, `agent`, `gpu`, `cpu`, and `ram`. Measurement blocks
have an explicit `observed`, `not_observed`, or `unavailable` status. Values are
numbers or `null`; absence is never represented as a fabricated zero.
Schema 2 has exact agent keys `version`, `sample_interval_seconds`,
`priority_requested`, `priority_application_result`, and
`priority_observed_effective`.

## Historical initial deployment and installation reference

Version 1.0.0 of this package was the physically deployed and qualified initial
baseline. Version 1.0.1 was later observed deployed as recorded above. These scripts
do not grant installation or deployment authority; any new installation still
requires separate operator approval.

1. Copy the complete `telemetry_agent` directory to a reviewed temporary directory
   on `192.168.0.101` using the operator's approved file-transfer method.
2. On the 4090, inspect `agent.py`, this README, and all `windows/*.ps1` files.
3. In an elevated PowerShell on the 4090, run:
   `Set-ExecutionPolicy -Scope Process Bypass`.
4. Preview installation with:
   `.\windows\Install-GRACI4090Telemetry.ps1 -PythonExecutable '<absolute python.exe>' -WhatIf`.
5. Run the same command without `-WhatIf`. It copies four package files to
   `C:\ProgramData\GRACI\telemetry_agent`, registers a limited SYSTEM startup
   task, and creates the fixed firewall rule. It does **not** start the task.
6. Verify the installed files, scheduled-task action, SYSTEM/limited principal,
   firewall local/remote addresses, port, profile, and program allowlist.
7. Start only the named task with `.\windows\Start-GRACI4090Telemetry.ps1`.
8. Run `.\windows\Status-GRACI4090Telemetry.ps1` locally on the 4090, then from the
   3090 fetch `/health` and `/telemetry`. Confirm `node_id` is `4090`, GPU name is
   RTX 4090, timestamps advance about every 3 seconds, and CPU temperature is null.
9. Confirm the existing MO2/llama endpoint and its policy behavior are unchanged.
10. In a separately approved physical-QA window, restart the 4090 and execute the
    reboot acceptance procedure below.

## Automatic startup contract

The installer registers exactly one startup mechanism: the Windows scheduled task
`GRACI 4090 Read-Only Telemetry`. Its trigger is `AtStartup`, its principal is the
limited `SYSTEM` service account, and its fixed action is the reviewed Python
executable with `-m telemetry_agent` in `C:\ProgramData\GRACI`. No user login is
required. `MultipleInstances IgnoreNew` prevents duplicates; at most three
one-minute restart attempts prevent a rapid restart loop. The task starts no model,
llama.cpp process, MO2 process, or workload policy service. The remove script
unregisters this task and its one firewall rule without adding another persistence
mechanism.

The expected startup workload is the same three-second, mostly sleeping sampler.
It must not delay Windows or gaming readiness in any meaningful way. Below-normal
priority is requested and independently observed; no E-core affinity is used.

## Update and rollback

After the 3090 has been updated to the compatible client, use this explicit update
sequence on the 4090 in an elevated PowerShell. No reboot is required:

1. Transfer the corrected `telemetry_agent` directory to a reviewed staging path,
   replace the first variable below with that absolute path, and inspect every
   staged Python, JSON, README, and PowerShell file.
2. Run the following in an elevated PowerShell on the 4090:

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   $StagedPackage = '<reviewed-staging-path>\telemetry_agent'
   $InstallRoot = 'C:\ProgramData\GRACI\telemetry_agent'
   $RollbackRoot = Join-Path 'C:\ProgramData\GRACI\rollback' `
       ('telemetry-agent-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
   $PackageFiles = @('__init__.py', '__main__.py', 'agent.py', 'config.defaults.json')

   & (Join-Path $StagedPackage 'windows\Stop-GRACI4090Telemetry.ps1')
   $Task = Get-ScheduledTask -TaskName 'GRACI 4090 Read-Only Telemetry' -ErrorAction Stop
   if ($Task.State -ne 'Ready') { throw 'Telemetry task did not stop cleanly.' }

   New-Item -ItemType Directory -Path $RollbackRoot -Force | Out-Null
   foreach ($File in $PackageFiles) {
       Copy-Item -LiteralPath (Join-Path $InstallRoot $File) -Destination $RollbackRoot
       Copy-Item -LiteralPath (Join-Path $StagedPackage $File) -Destination $InstallRoot -Force
   }

   $Task | Select-Object TaskName, State, Actions, Triggers, Principal, Settings
   & (Join-Path $StagedPackage 'windows\Start-GRACI4090Telemetry.ps1')
   & (Join-Path $StagedPackage 'windows\Status-GRACI4090Telemetry.ps1')
   ```

3. Confirm the unchanged task still has its `AtStartup` trigger, limited `SYSTEM`
   principal, fixed action, `IgnoreNew`, and bounded restart settings. Do not
   register a second startup mechanism.
4. Verify `/health` reports schema 2 ready and `/telemetry` reports agent version
   1.0.1, advancing observations, requested priority `below_normal`, a truthful
   application result, and observed effective priority `below_normal`.
5. From the 3090 verify the HUD reacquires fresh live telemetry while 4090 workload
   eligibility remains independently fail-closed.

Rollback is equally explicit: run the staged stop script, copy the same four files
from the recorded `$RollbackRoot` back to `$InstallRoot` with `-Force`, run the
staged start script, and repeat the route/identity/freshness checks.
To disable the feature, run `Remove-GRACI4090Telemetry.ps1`; it removes only the
named startup task and firewall rule and retains files for inspection. GRACI fails
closed to unavailable telemetry.

## Separately approved reboot acceptance procedure

1. Record the named task action, trigger, principal, settings, current process ID,
   priority, MO2 state, and llama.cpp/model state. Confirm one agent process.
2. Reboot Windows normally. Do not issue a manual telemetry start command.
3. Confirm `GRACI 4090 Read-Only Telemetry` started from its boot trigger without a
   user login and that exactly one fixed telemetry-agent process exists.
4. Confirm the process is Below Normal, listens only on `192.168.0.101:8767`, and
   `/health` returns ready.
5. Fetch `/telemetry` twice more than three seconds apart. Confirm schema/node/GPU
   identity, fresh advancing timestamps, and real GPU/CPU/VRAM/RAM observations.
6. Confirm the 3090 HUD automatically returns to `LIVE TELEMETRY` within its normal
   polling/freshness window while eligibility remains a separate fail-closed fact.
7. Recheck working set, private memory, CPU, GPU compute, VRAM allocation, and HTTP
   latency against the qualified baseline. Confirm no duplicate or rapid restart.
8. Confirm llama.cpp/model state and MO2/gaming behavior are unchanged by startup.

## Resource expectations

The physically qualified 4090 deployment measured about 42 MiB working set,
30 MiB private memory, effectively negligible CPU, no attributable GPU compute or
VRAM allocation, and about 0.4 ms HTTP latency. The process is mostly sleeping: one
sensor sample occurs every three seconds and HTTP replies serialize cached data
without hardware work. Requalify these measurements after the source update.
E-core affinity is not implemented and correctness never depends on topology or
affinity.
