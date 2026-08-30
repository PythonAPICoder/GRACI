# GRACI 4090 read-only telemetry agent

This standalone Windows package exposes cached presentation telemetry from the
optional 4090 node. It does not expose a shell, command execution, filesystem,
process, model, configuration, generic RPC, or write endpoint. It cannot make the
4090 eligible and does not modify the existing MO2/llama policy endpoint.

## Fixed production contract

- Python standard library only; no pip dependencies.
- Direct, persistent NVML access for exact GPU identity, utilization, VRAM bytes,
  and GPU temperature. It never polls `nvidia-smi`.
- Native `GetSystemTimes` and `GlobalMemoryStatusEx` for CPU utilization and RAM.
  CPU temperature is `null` / `not observed` because Windows has no safe,
  dependency-free sensor API for it.
- Sampling every 3 seconds into a bounded cache. Requests never sample hardware.
- Below-normal process priority is requested at startup. Correctness does not rely
  on it. No CPU affinity or hard-coded CPU IDs are used.
- `GET http://192.168.0.101:8767/health`
- `GET http://192.168.0.101:8767/telemetry`
- Schema version 1, fixed object keys, maximum 16 KiB response.
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

## Proposed deployment (requires separate operator approval)

These scripts are packaged for later execution on the 4090. They were not run by
this change.

1. Copy the complete `telemetry_agent` directory to a reviewed temporary directory
   on `192.168.0.101` using the operator's approved file-transfer method.
2. On the 4090, inspect `agent.py`, this README, and all `windows/*.ps1` files.
3. In an elevated PowerShell on the 4090, run:
   `Set-ExecutionPolicy -Scope Process Bypass`.
4. Preview installation with:
   `.\windows\Install-GRACI4090Telemetry.ps1 -PythonExecutable '<absolute python.exe>' -WhatIf`.
5. Run the same command without `-WhatIf`. It copies three package files to
   `C:\ProgramData\GRACI\telemetry_agent`, registers a limited SYSTEM startup
   task, and creates the fixed firewall rule. It does **not** start the task.
6. Verify the installed files, scheduled-task action, SYSTEM/limited principal,
   firewall local/remote addresses, port, profile, and program allowlist.
7. Start only the named task with `.\windows\Start-GRACI4090Telemetry.ps1`.
8. Run `.\windows\Status-GRACI4090Telemetry.ps1` locally on the 4090, then from the
   3090 fetch `/health` and `/telemetry`. Confirm `node_id` is `4090`, GPU name is
   RTX 4090, timestamps advance about every 3 seconds, and CPU temperature is null.
9. Confirm the existing MO2/llama endpoint and its policy behavior are unchanged.
10. Restart the 4090 during an approved window; verify automatic startup, bounded
    resource use, and fresh observations on the GRACI HUD.

## Update and rollback

Stop the named task, archive the installed package files, review and copy the new
package files, then restart and repeat identity/freshness/resource checks. To roll
back, stop the task and restore the archived files. To disable the feature, run
`Remove-GRACI4090Telemetry.ps1`; it removes only the named task and firewall rule
and retains files for inspection. GRACI fails closed to unavailable telemetry.

## Resource expectations

The persistent Python process is mostly sleeping. One sensor sample occurs every
three seconds and HTTP replies serialize no hardware work. Development-host
measurements belong in project status documentation; target 14900K/4090 CPU,
memory, latency, temperature, and power impact remain unverified until the approved
deployment QA above. Optional future E-core affinity would have to discover Windows
CPU sets dynamically (for example through `GetSystemCpuSetInformation`); it is not
implemented and correctness never depends on topology or affinity.
