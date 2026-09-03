# Historical Phase 8E Stage 2 Windows boundary plan

> Classification: historical incident evidence
> Authority: PO-DEC-028, PO-DEC-029, PO-DEC-030, ACC-0007, and ACC-0008
> Baseline: `4369cb9373d9b6211d0d69d30a29408e520272de`
> Prepared: 2026-09-02
> State: UNSAFE AND REJECTED BY PO-DEC-039; DO NOT EXECUTE

This document preserves the exact design that caused the Phase 8E Stage 2
host-safety incident. Its claims that SID-scoped AppLocker deny rules and broad
compatibility allows preserved ordinary host behavior are incorrect. It is not a
current plan, deployment procedure, or authority source. See
[`INC-0001`](incidents/INC-0001-phase8e-stage2-applocker.md),
[`ACC-0012`](acceptance/ACC-0012-phase8e-incident-response.md), and the
[`replacement design`](PHASE_8E_REPLACEMENT_BOUNDARY_DESIGN.md).

## Observed host facts

Read-only inspection was performed on `AI-SERVER` before dependent host mutation.
The host runs Windows 11 Pro build 26200 in a local workgroup. The active operator
is `AI-SERVER\Steve`, SID
`S-1-5-21-80404339-2367555055-2558411261-1001`. Its ordinary token is not elevated,
but the account is a local administrator and an elevated read-only inspection
completed through Windows consent without requesting or exposing a password.

The `E:` volume is healthy NTFS. `E:\GRACI-Review-Staging` and
`E:\GRACI-Review-Projection` do not exist. The proposed `GRACI_Review` local account
does not exist. `C:\ProgramData\GRACI\Phase8E` does not exist.

The Application Identity service is running with its existing Manual start type.
The effective AppLocker policy is empty. Windows Code Integrity separately enforces
the signed `VerifiedAndReputableDesktop` policy
`0283ac0f-fff1-49ae-ada1-8a933130cad6`, which has Intelligent Security Graph
authorization and supplemental-policy support enabled. Its script-enforcement
option is disabled. Stage 2 will not modify, replace, disable, or relax that policy.

The `E:` volume has no associated BitLocker volume. Stage 2 uses synthetic content
only. This is a recorded at-rest residual risk and prevents any claim that the host
currently supplies the recommended encrypted storage for a later sensitive or
real-data projection.

## Exact selected boundary

The dedicated viewer is `AI-SERVER\GRACI_Review`. Installation creates it as an
enabled standard local user with a generated high-entropy password that is never
printed, logged, written, returned, or placed in source. It is not added to
Administrators or any GRACI role. Its resolved SID is recorded after creation and
is used directly in ACL and AppLocker rules. The account cannot change its password.

The independent sibling roots are:

- staging: `E:\GRACI-Review-Staging`
- promoted projection: `E:\GRACI-Review-Projection`
- launcher foundation: `C:\ProgramData\GRACI\Phase8E`
- operational evidence and exact prechange backup: `E:\GRACI-Review-Evidence`

The repository inputs tested for viewer isolation are the saved repository
`E:\GRACI` and this separate worktree
`C:\Users\Steve\.codex\worktrees\2c0c\GRACI`. No governed-memory root is selected
or inspected in Stage 2.

Each new root receives a protected DACL. The exact access matrix is:

| Principal | Staging | Projection | Launcher and evidence |
|---|---|---|---|
| `NT AUTHORITY\SYSTEM` (`S-1-5-18`) | Full control | Full control | Full control |
| `BUILTIN\Administrators` (`S-1-5-32-544`) | Full control | Full control | Full control |
| `AI-SERVER\Steve` (`S-1-5-21-80404339-2367555055-2558411261-1001`) | Modify, synchronize, and inherited child access | Modify, synchronize, and inherited child access | Full control |
| `AI-SERVER\GRACI_Review` | No allow ACE | Read, execute, synchronize, and traverse only | Read and execute only |

Both repository roots receive an explicit viewer-SID deny ACE for FullControl on
the root with object and container inheritance. The deny is deliberately scoped to
the dedicated viewer SID. Existing grants for all other identities remain unchanged.
The viewer receives no staging ACE and cannot list or traverse it. Projection child
files inherit only read and execute rights for the viewer, with no write, append,
create, delete, delete-child, rename, ownership, or DACL-change right.

## Application control

Stage 2 adds a local AppLocker policy scoped by SID and leaves WDAC unchanged. The
Executable, Windows Installer, Script, and DLL collections are enforced. Each
collection contains an `Everyone` allow rule for `*`, preserving the host's prior
AppLocker behavior, plus deny rules for the viewer SID at both
`E:\GRACI-Review-Staging\*` and `E:\GRACI-Review-Projection\*`. AppLocker deny rules
take precedence over the compatibility allow rule. Other users therefore retain
their prior AppLocker behavior while the dedicated viewer cannot execute code from
either Stage 2 root. Existing effective AppLocker XML and service state are captured
before the change.

The policy is selected because Windows 11 exposes the local AppLocker enforcement
surface, the Application Identity service is live, and the current AppLocker policy
is empty. It supplements the stronger enforced WDAC reputation policy and does not
change WDAC files, options, authorization, audit state, Smart App Control, signing,
or trust settings.

## Commands and launcher behavior

The elevated apply and reapply command is:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\install-phase8e-review-boundary.ps1
```

The read-only verification command is:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\verify-phase8e-review-boundary.ps1
```

After the Stage 1 exporter performs its same-volume directory move, the operator
runs the following bounded finalization before viewer use:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\finalize-phase8e-projection.ps1
```

Windows preserves the staging directory ACL during a same-volume move. The
finalizer resolves only the canonical UUID selected by `current.json`, rejects
reparse points and containment failures, and resets that generation tree to inherit
the protected projection-root ACL. Until this succeeds, viewer access fails closed
and the launcher verification rejects the generation.

The bounded launcher installed under `C:\ProgramData\GRACI\Phase8E` first verifies
the expected viewer SID, root containment, reparse-point absence, projection ACL,
AppLocker rules, current pointer, manifest hash, listed output hashes, and absence
of unmanifested files. Stage 2 installs no qualified application record. An open
request therefore ends with `APPLICATION_NOT_QUALIFIED` before starting any process.
A future Stage 3 record must name an exact executable path, SHA-256 hash, publisher,
and signature state before the launcher can become launch-capable.

## Validation sequence

The implementation performs these bounded synthetic cases:

1. Apply the account, roots, DACLs, source-deny ACEs, AppLocker rules, and launcher.
2. Export the accepted Stage 1 synthetic repository and memory fixtures as the
   exporter identity, then verify promotion and viewer read access.
3. Run actual viewer-token probes for source and staging denial, projection read,
   projection create, edit, append, delete, rename, ownership, and DACL denial.
4. Place benign executable and PowerShell probes in a synthetic projection
   generation as the exporter and prove AppLocker denies both under the viewer SID.
5. Tamper with a copied generation as the exporter and prove verify-on-open detects
   it before any application launch.
6. Force a synthetic failed refresh and prove `current.json` and the complete last
   known good generation remain byte-for-byte unchanged.
7. Temporarily withhold the projection, confirm the resident browser endpoint on
   port 8766 remains responsive, restore the projection, and verify it again.
8. Run exact rollback, prove the account, policy rules, installed launcher, roots,
   and source-deny ACEs are removed or restored, then reapply and repeat the focused
   boundary checks.

The procedure does not stop the resident, use real memory, install or launch
Obsidian, alter network or firewall policy, schedule refresh, or touch the 4090.

## Evidence and exact rollback

Sanitized evidence is written to `phase8e/evidence/` in this worktree. Exact local
prechange AppLocker XML, service state, source ACL SDDL, and root-existence facts are
stored under `E:\GRACI-Review-Evidence\prechange`. Evidence never contains the
generated account password or excluded fixture content.

The elevated rollback command is:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\remove-phase8e-review-boundary.ps1
```

Rollback first restores the captured AppLocker XML and original Application
Identity service state, removes only the viewer-SID deny ACEs from the two named
repository roots, removes the protected Stage 2 launcher, staging, and projection
roots, removes only the unloaded profile whose recorded SID and bounded
`C:\Users\GRACI_Review*` path match, and finally deletes only the exact
`GRACI_Review` local account created by the procedure. It preserves the evidence
root and prechange backup. The rollback
script refuses unknown paths, reparse points, missing backup identity, or a viewer
SID mismatch. Reapply uses the same names and rights but records the newly assigned
local SID.

Automated verification, live host observation, local boundary configuration, and
Product Owner acceptance remain distinct. The Product Owner accepted this Stage 2
scope on 2026-09-02. This plan does not claim full Phase 8E acceptance.

## Subsequent Product Owner storage decision

After the Stage 2 evidence exposed the absence of BitLocker, the Product Owner
accepted unencrypted local storage as an intentional physical-security risk for the
two home systems. BitLocker must not be installed, enabled, configured, or deployed
on any drive, folder, or file on either system. This removes BitLocker as a Phase 8E
prerequisite without authorizing real data, Stage 3, Stage 4, or Stage 2 acceptance.

## Product Owner acceptance

On 2026-09-02, the Product Owner separately accepted Stage 2 and authorized its
commit and push to `main`. Obsidian inspection or configuration, real data, network
or firewall changes, automatic refresh, runtime integration, and later stages remain
unauthorized.
