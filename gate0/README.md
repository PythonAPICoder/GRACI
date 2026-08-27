# GRACI Gate 0 Environment Qualification

Run date: 2026-08-27 (America/Chicago)
Workspace: `E:\GRACI`
Host context: 3090 Server / Codex Work environment

No software was installed, no service was changed or restarted, no firewall or system configuration was changed, and no commit was created.

## Results

| Test | Status | Evidence |
|---|---|---|
| G0.1 Workspace access | PASS | Inspected the clean workspace. Created `gate0_workspace_probe.tmp`, read `gate0 probe: created`, changed it to `gate0 probe: modified`, read the changed value, then deleted it and verified it no longer existed. |
| G0.2 Command execution | PASS | Direct local command execution works. Shell: PowerShell Core 7.6.4. Working directory: `E:\GRACI`. |
| G0.3 Python | PASS | Python 3.14.7. Executable: `C:\Python314\python.exe`. No packages installed. |
| G0.4 Git | PASS | Git 2.55.0.windows.3 at `C:\Program Files\Git\cmd\git.exe`. Workspace was not initially a repository. Initialized an empty repository with initial branch `main`; no commit created. The Codex sandbox account sees a Git dubious-ownership warning because the workspace belongs to the desktop user, so checks used a per-command `safe.directory` override without modifying global configuration. |
| G0.5 3090 local inference | PASS | `GET http://127.0.0.1:8080/v1/models` returned HTTP 200. Model IDs: `GLM-4.7-Flash-64x2.6B-Q4_K_M`, `qwen3.8-27b-q4_k_m`. Standard loopback alternatives 1234, 11434, 8000, 5000, and 5001 refused connections. |
| G0.6 4090 inference node | PASS | `GET http://192.168.0.101:8080/v1/models` returned HTTP 200. Model IDs: `GLM-4.7-Flash-64x2.6B-Q4_K_M`, `qwen3.8-27b-q4_k_m`. |
| G0.7 4090 scheduling prerequisite | BLOCKED | Existing remote-management ports were detectable (WinRM HTTP 5985, SMB 445, RPC 135 open; WinRM HTTPS 5986 unavailable), but a read-only remote `tasklist` query failed with `The user name or password is incorrect`. This environment therefore has no currently usable, authenticated, safe mechanism to determine whether `ModOrganizer.exe` is running remotely. No credentials were requested or inspected. |
| G0.8 Persistence | PASS | This directory contains the durable human-readable report and machine-readable `results.json`. |

## Overall

**GATE 0 OVERALL: PARTIAL**

Core autonomous development operations and the primary 3090 inference path are operational. Both inference endpoints are reachable. The optional 4090 process-state scheduling prerequisite remains unresolved.

## Minimum next action for blocked item

- G0.7: Later, choose and authorize a least-privilege remote status mechanism that can report only whether `ModOrganizer.exe` is running (for example, a constrained authenticated WinRM/JEA command or a small authenticated LAN-only health/status endpoint). Then provide this Work environment access to that mechanism and retest. No such configuration should be made during Gate 0.
