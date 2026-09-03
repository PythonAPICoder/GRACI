# Phase 8E read-only host audit

> Classification: executed audit design and historical procedure
> Design authority: PO-DEC-039
> Closure authority: PO-DEC-040
> State: GATES 1, 2, AND 3 PASSED; OPERATIONALLY CLOSED

The Product Owner separately authorized execution after this plan was written.
Gate 1, Gate 2, and post-reboot Gate 3 passed. The accepted result is
`FUNCTIONAL WITH HARMLESS RESIDUE`; exact final evidence is preserved in
[`ACC-0013`](acceptance/ACC-0013-phase8e-applocker-operational-closure.md). This
document remains the reviewed procedure and does not authorize rerunning it.

## Question

Determine whether any effective or residual Phase 8E Stage 2 AppLocker state remains
without changing the host. Do not assume residue exists or does not exist from the
fact that Windows is currently functional.

## Exact scope

The audit is limited to the recovered 3090 Windows host and the following read-only
observations:

1. OS identity, edition, build, current boot time, and audit timestamp.
2. Presence and values under
   `HKLM\SOFTWARE\Policies\Microsoft\Windows\SrpV2` and other exact AppLocker
   effective-policy locations identified by Windows documentation before approval.
3. Local and effective AppLocker XML through `Get-AppLockerPolicy`, captured without
   applying, merging, exporting back, or restoring policy.
4. `AppIDSvc`, `appid`, and `applockerfltr` status, start mode, dependencies, and
   process ownership through read-only service queries.
5. Names, sizes, timestamps, hashes, owners, and ACL text for files already present
   under `C:\Windows\System32\AppLocker`. The audit must not open files for write,
   delete them, rename them, replace them, or infer active enforcement merely from
   their existence.
6. AppLocker EXE/DLL, MSI/Script, and Packaged App execution and deployment event
   logs covering the incident and all later boots.
7. Relevant Code Integrity events reported separately so Smart App Control or WDAC
   evidence is not conflated with AppLocker.
8. Presence and hashes of the historical GRACI policy and boundary-state artifacts,
   without using them to change the host.
9. Non-destructive launch checks for Codex, Snipping Tool, classic PowerShell, the
   Product Owner's normal PowerShell or Terminal path, Command Prompt, and one other
   packaged Windows application, only if the separately approved audit explicitly
   includes those launches.

## Proposed read-only commands

The final approval request must reproduce the exact reviewed commands. The intended
command families are:

```powershell
Get-CimInstance Win32_OperatingSystem
Get-ItemProperty -LiteralPath 'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Microsoft\Windows\SrpV2'
Get-AppLockerPolicy -Local
Get-AppLockerPolicy -Effective
Get-CimInstance Win32_Service -Filter "Name='AppIDSvc' OR Name='appid' OR Name='applockerfltr'"
Get-ChildItem -LiteralPath 'C:\Windows\System32\AppLocker' -Force
Get-FileHash -LiteralPath <exact-existing-file> -Algorithm SHA256
Get-Acl -LiteralPath <exact-existing-path>
Get-WinEvent -FilterHashtable <exact-AppLocker-or-Code-Integrity-filter>
```

`reg query`, `sc query`, and `sc qc` may be used only as read-only corroboration.
No command containing `Set`, `New`, `Remove`, `Clear`, `Start`, `Stop`, `Restart`,
`Enable`, `Disable`, `config`, `delete`, `add`, or an output redirection into a host
location belongs in the approved command set.

## Evidence and interpretation

Capture command, timestamp, exit status, bounded output, and SHA-256 for the audit
report. Redact no failure that affects interpretation. Classify each finding as:

- effective policy evidence;
- persisted but not proven effective state;
- historical event evidence;
- unrelated Code Integrity evidence;
- absent or inaccessible evidence;
- inconclusive.

Do not call the host clean solely because the registry key is absent. Do not call
the host affected solely because cache files exist. Reconcile policy, service,
cache, event, boot, and application-launch observations.

## Explicit exclusions

The audit does not reboot, log out, restart a service, change service configuration,
apply or remove policy, modify registry data, change ACLs, create an account, change
a firewall rule, clear logs, delete cache, run recovery tools, deploy the replacement
boundary, or perform cleanup. Any newly discovered need for mutation requires a new
Host System Change Approval request and another stop.

## Completion condition

Return a signed or hashed read-only evidence bundle and a plain-language conclusion
with uncertainty stated. Stop for Product Owner review. Do not remediate findings
under the audit authority.
