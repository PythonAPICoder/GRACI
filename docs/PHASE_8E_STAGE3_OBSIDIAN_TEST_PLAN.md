# Phase 8E Stage 3 Obsidian candidate test plan

> Classification: historical implementation evidence
> Authority: PO-DEC-031
> Baseline: `b57662a1373990a2953540209f3a901770ebc0b7`
> State: TEST FAILED CLOSED; ROLLBACK VERIFIED

> Current notice: this is historical test evidence. PO-DEC-039 rejects the Stage 2
> AppLocker dependency and quarantines the associated host workflow. Do not execute
> this plan.

## Authorized result

The existing Obsidian installation may be made readable and executable by the
dedicated `AI-SERVER\GRACI_Review` account, protected by an outbound firewall rule
that applies only to that account, and tested against the existing synthetic Phase
8E projection. The test may create Obsidian settings only in the review account's
profile. It must not inspect or alter the Product Owner's Obsidian settings.

This authorization does not include real governed memory, real projection data,
community plugins, automatic refresh, ordinary GRACI runtime integration, changes
to the Product Owner's access, or BitLocker changes.

## Exact candidate

- executable: `C:\Users\Steve\AppData\Local\Programs\Obsidian\Obsidian.exe`
- shell version: `1.13.4`
- SHA-256: `c01bbd79583037639f5422396cddb457ef48e89e159ca50a8492bbd1f1f10775`
- Windows signature state: valid
- signer: `CN=Dynalist Inc, O=Dynalist Inc, L=Oakville, S=Ontario, C=CA`
- signer thumbprint: `20B5809A5B1C52EB05EC7672673920913E0ED26D`

The exact executable and its containing tree have no observed reparse points. The
installation is per-user and currently grants access only to the Product Owner,
Administrators, and SYSTEM. The review account therefore cannot use it until the
new exact-folder read-and-execute rule is applied.

## Exact Windows changes

1. Save the existing Obsidian-folder security descriptor and confirm that no
   matching GRACI firewall rule exists.
2. Add inheritable read-and-execute access for the exact review SID only at the
   Obsidian installation root. Do not change the Product Owner's existing access.
3. Add one enabled outbound block rule for the exact executable and exact review
   SID. The rule must not apply to the Product Owner's account.
4. Run the candidate under the actual review token with the current synthetic
   generation. Confirm projection read, projection write denial, process start,
   review-profile configuration, no non-loopback established connection, and no
   projection change.
5. Keep the Stage 2 launcher unqualified. A successful candidate test is not
   permission for routine launch or full Phase 8E acceptance.

Any mismatch, unsafe path, signature failure, unexpected existing rule, failed test,
or unknown state fails closed. A failed test restores the saved folder permissions,
removes the exact firewall rule, and removes only test-created review-profile state.

## Observed result

The actual review token could read the exact signed Obsidian executable and the
synthetic projection. Its attempted projection write was denied, the projection
remained unchanged, and no non-loopback established connection was observed.
Obsidian did not remain running and did not register the synthetic vault in the
review profile. No AppLocker, Code Integrity, application-crash, or Windows Error
Reporting event identified a policy or crash cause.

The candidate therefore failed qualification. Automatic rollback restored the
original Obsidian-folder permissions, removed the exact firewall rule, removed
test-created review-profile state, and left no Obsidian process. The executable
hash and valid signature were unchanged. The accepted Stage 2 boundary still passed,
and the resident GRACI page still returned HTTP 200.

Further testing requires a new Product Owner decision. The recommended next option
is a separate Obsidian installation or copy owned by the review account so the
Product Owner's existing per-user installation and settings remain untouched.

## Rollback

`ops/remove-phase8e-obsidian-test.ps1` restores the saved Obsidian-folder security
descriptor, removes only the exact verified firewall rule, removes the copied test
worker and unqualified candidate state, and removes the review account's Obsidian
settings only if they did not exist before this test. It preserves evidence.
