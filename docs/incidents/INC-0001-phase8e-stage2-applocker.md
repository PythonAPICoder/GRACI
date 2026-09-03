# INC-0001: Phase 8E Stage 2 AppLocker host-safety incident

> Classification: durable high-severity incident record
> Severity: HIGH
> State: ROOT CAUSE ACCEPTED; REPOSITORY REMEDIATION AUTHORIZED
> Incident date: 2026-09-02
> Accepted authority: PO-DEC-039

## Executive summary

Phase 8E Stage 2 enabled machine-wide AppLocker enforcement to prevent the
dedicated review identity from executing files in two review directories. The
generated policy enabled the EXE, DLL, MSI, and Script collections but did not
create a Packaged App collection. Windows therefore blocked packaged applications
and repeatedly recorded AppLocker Event 8027:

```text
No packaged apps can be executed while Exe rules are being enforced and no
Packaged app rules have been configured.
```

Codex, Snipping Tool, and the Product Owner's PowerShell launch path stopped
working and displayed that the system administrator had blocked the application.
Windows still booted, login remained available, and elevated Command Prompt still
worked. The event began while the Stage 2 policy was being applied and stopped only
after incident recovery.

This was a serious host-safety failure. The AppLocker architecture is unsafe,
rejected, not approved for deployment, and not part of the current GRACI baseline.
Adding a broad Packaged App allow rule is not an approved remediation.

## Root cause

`New-Phase8EAppLockerXml` in
[`phase8e-review-boundary-common.ps1`](../../ops/phase8e-review-boundary-common.ps1)
generated four enabled rule collections and no Packaged App collection. It added
an Everyone `Allow *` rule to each configured collection and described those rules
as preserving the prior empty-policy behavior. That assumption was incorrect.

AppLocker rule targeting and collection enforcement have different scopes. The
deny rules named one viewer SID, but enabling the EXE collection changed
machine-wide behavior. An EXE allow rule does not authorize an application governed
by the separate Packaged App collection.

[`install-phase8e-review-boundary.ps1`](../../ops/install-phase8e-review-boundary.ps1)
then applied the generated XML with:

```powershell
Set-AppLockerPolicy -XmlPolicy $policyPath
```

The resulting machine policy was stored under
`HKLM\SOFTWARE\Policies\Microsoft\Windows\SrpV2`. This global control was
disproportionate to the narrow requirement to protect
`E:\GRACI-Review-Staging\*` and `E:\GRACI-Review-Projection\*` from one standard
viewer identity.

## Affected implementation

- `ops/phase8e-review-boundary-common.ps1` generated the incomplete enforced
  policy and the incorrect compatibility claim.
- `ops/install-phase8e-review-boundary.ps1` installed the policy and started
  Application Identity when necessary.
- `ops/verify-phase8e-review-boundary.ps1` required only the four configured
  collections and never checked Packaged App behavior.
- `ops/test-phase8e-review-boundary.ps1` tested viewer denial with classic
  executables and scripts but not packaged applications or general host usability.
- `ops/remove-phase8e-review-boundary.ps1` restored saved policy XML and limited
  service state but did not model compiled or cached policy state or reboot recovery.
- `ops/open-phase8e-review.ps1` treated the rejected AppLocker policy as a routine
  launcher prerequisite.
- `tests/test_phase8e_stage2_boundary.py` statically approved the four-collection
  policy and broad allow rules instead of detecting the missing application class.
- `docs/PHASE_8E_STAGE2_WINDOWS_PLAN.md`, `ACC-0008`, and later current-state
  documents incorrectly described the boundary as safe, viewer-scoped, and
  compatibility-preserving.

The implementation entered `main` in commit
`b57662a1373990a2953540209f3a901770ebc0b7`. Later Stage 3 work depended on that
boundary, so its application qualification evidence remains historical but its
routine-launch approval is no longer current.

## User impact

- Packaged Windows applications stopped launching.
- Codex and Snipping Tool were unavailable.
- The Product Owner's PowerShell launch path was unavailable.
- Recovery required elevated Command Prompt and then Windows Recovery Environment.
- Normal application execution remained disrupted for several hours.

The available AppLocker EXE log later showed classic
`WindowsPowerShell\v1.0\powershell.exe` as allowed. The exact blocked PowerShell
presentation was therefore likely a packaged host, alias, or related packaged
component, but the preserved evidence does not identify it precisely.

## Timeline

- At 13:30 CDT, Stage 2 captured an empty pre-change AppLocker policy.
- At 13:35:03, the first Packaged App Event 8027 was recorded.
- At 13:49:39, the Stage 2 boundary was recorded as applied or reapplied.
- At 14:26:23, commit `b57662a` recorded Stage 2 acceptance.
- Event 8027 continued until 23:33:57.
- Removing the GRACI-created registry policy and rebooting did not restore packaged
  application execution.
- In Windows Recovery Environment, `AppCache.dat` was removed offline.
- Windows booted at 23:42:17, affected applications worked again, and no later
  Event 8027 was observed in the incident review.

The repository and event timing establish the policy defect and the packaged-app
failure directly. The recovery sequence strongly supports retained compiled or
cached AppLocker state after registry removal. Because the cache deletion was not
reproduced as a controlled experiment, it is evidence from the actual recovery,
not a claim that cache-file existence alone proves active enforcement.

The earlier Code Integrity Event 3077 concerning a Codex runtime `pwsh.exe` loading
a llama.cpp executable occurred on the previous day under
`VerifiedAndReputableDesktop`. It involved a different subsystem and executable and
is not evidence for the later packaged-app outage.

## Recovery

The Product Owner removed the GRACI-created `SrpV2` registry policy, rebooted,
entered Windows Recovery Environment when blocking continued, removed the remaining
`AppCache.dat` offline, and rebooted again. Codex, Snipping Tool, and PowerShell then
worked again.

This record does not assert whether AppLocker residue currently exists. The host is
functional, and no further inspection or cleanup is authorized by PO-DEC-039. A
separate read-only audit requires a later explicit decision.

## Why validation failed

The Stage 2 suite proved viewer ACL and path-denial cases, tamper detection,
failed-refresh preservation, immediate XML rollback, and resident independence. It
did not test Packaged App policy, Codex, Snipping Tool, the Product Owner's
PowerShell launch path, general host usability, reboot behavior, or usability after
rollback and reboot. Immediate empty policy XML was incorrectly treated as adequate
rollback evidence.

## Lessons learned

1. A user-specific rule does not make a host security subsystem user-local.
2. Broad allow rules in one application class do not authorize other application
   classes.
3. Machine-wide application control was disproportionate to this viewer boundary.
4. Registry state is not sufficient evidence of effective-policy rollback.
5. Host-level changes need exact informed approval, isolated validation, normal-app
   safety tests, reboot tests, and complete recovery planning.
6. Application-local controls are preferred to user-local controls, and user-local
   controls are preferred to machine-wide enforcement.

## Current disposition

- The original AppLocker design and dependent launcher are quarantined in the
  repository under PO-DEC-039.
- Historical source and evidence remain intact in current files below the fail-closed
  guard, in commit `b57662a`, and in the original evidence records.
- A non-AppLocker replacement is approved for design only.
- No replacement deployment, host audit, host cleanup, or Phase 8F work is
  authorized by this record.
