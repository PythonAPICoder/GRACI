# ACC-0008: Phase 8E Stage 2 Windows boundary technical record

> Classification: durable automated, live validation, and acceptance record
> State: PRODUCT OWNER ACCEPTED
> Recorded: 2026-09-02

## Verified scope

The authorized Stage 2 procedure implemented the synthetic local Windows viewer
boundary on `AI-SERVER`. The final account is the standard local identity
`AI-SERVER\GRACI_Review`, SID
`S-1-5-21-80404339-2367555055-2558411261-1007`. Staging and projection are separate
siblings on NTFS `E:`. The viewer has no source or staging access and has read and
traverse access only to promoted projection content.

The host's enforced `VerifiedAndReputableDesktop` WDAC policy was observed and left
unchanged. A local AppLocker layer enforces viewer-SID path denies for executable,
installer, script, and DLL collections at both Stage 2 roots. Executable and
PowerShell probes were denied under the actual viewer token. The launcher verified
the selected manifest and outputs, detected tampering, and refused to start an
application because Stage 2 contains no qualified application record.

The final synthetic generation is
`8e000002-0000-4000-8000-000000002001` with 25 manifest entries. Actual viewer-token
tests passed projection read, source and staging denial, create, edit, append,
delete, rename, ownership, and permission-change denial. A failed refresh left the
last known good tree unchanged. Withholding `current.json` left the live GRACI
resident browser responsive with HTTP 200.

Exact rollback removed the account, managed roots, AppLocker rules, and both
source-deny ACEs, removed the exact unloaded viewer profile, restored the empty
prechange AppLocker policy, preserved the evidence root, and left the resident
responsive. Reapply created a new SID and the full boundary passed again after the
required projection ACL finalization.

Machine-readable evidence is in
[`stage2-windows-20260902.json`](../../phase8e/evidence/stage2-windows-20260902.json).

## Product Owner acceptance

On 2026-09-02, the Product Owner accepted the Stage 2 synthetic Windows viewer
boundary and authorized its commit and push to `main`. Acceptance includes the
dedicated viewer identity, protected roots, source isolation, viewer-specific
application-control rules, exact ACL finalizer requirement, verification, rollback,
reapply, and recorded synthetic evidence.

## Observed limitation

`E:` has no associated BitLocker volume. Stage 2 used synthetic data only. This
record does not establish acceptable at-rest protection for a real or sensitive
projection. Windows also preserves the staging ACL during the same-volume directory
move. The new bounded finalizer must run before viewer use so the promoted generation
inherits the protected projection ACL. Until then, access fails closed.

After reviewing this limitation, the Product Owner accepted the lack of BitLocker
as an intentional physical-security risk and directed that BitLocker must not be
installed, enabled, configured, or deployed on any drive, folder, or file on either
system. This removes BitLocker as a Phase 8E prerequisite. It does not authorize
real data. The Product Owner subsequently accepted Stage 2 in a separate decision.

## Authority boundary

Stage 2 acceptance does not claim Obsidian qualification or configuration,
real-data validation, restart persistence, firewall isolation, human-interface
acceptance, or full Phase 8E acceptance. The Product Owner reports that Obsidian is
already installed but has never been used. Stage 2 did not inspect, open, configure,
or qualify that installation. No real governed memory was read, no network or
firewall rule changed, no automatic refresh or runtime integration was added, and
no Stage 3 work began.
