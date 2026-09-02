# Phase 8E Stage 1: read-only projection foundation

This stage implements the Product Owner-approved fixture-only foundation for a
one-way GRACI knowledge review projection. It adds a typed source catalog,
commit-pinned local Git reads, exact-ID synthetic memory reads, deterministic safe
Markdown rendering, complete manifests, source and output hashes, immutable
generations, atomic current-generation selection, and read-only tamper verification.

The exporter is deliberately separate from the `graci` package and ordinary runtime
composition. It makes no network request and no model call. It does not install or
configure Obsidian, inspect real governed memory, create a production projection,
change Windows security, run automatically, deploy, or grant authority.

Repository inputs must be exact regular UTF-8 Markdown blobs in a reviewed catalog
at a full local Git commit. Memory inputs must be exact canonical UUID JSON files
named by the caller. Metadata-only rendering is the default. Content appears only
for an exact requested ID that is also present in the approved-content set, and it
remains visibly marked as untrusted context.

Each successful export creates a complete generation under the projection root and
atomically updates `current.json` only after the generation passes hash and structure
verification. A failed build leaves the current pointer unchanged. Stage 1 uses only
the synthetic fixtures under `phase8e/fixtures/` and the focused test suite.

Run the focused verification with:

```powershell
python -W error -m unittest tests.test_phase8e_projection -v
```

Passing tests establish fixture behavior only. The Product Owner accepted this
bounded Stage 1 implementation on 2026-09-02; that decision does not establish
deployment, Windows isolation, Obsidian qualification, or real-data privacy.

## Stage 2 authorization boundary

The Product Owner accepted Stage 1 and authorized all Stage 2 work within the
accepted design on 2026-09-02. Stage 2 must inspect the available local Windows
security controls and record an exact supported plan before dependent mutation. The
plan must name the viewer account, same-volume sibling staging and projection roots,
ACL principals and rights, application-control mechanism, launcher and verification
commands, rollback procedure, validation cases, and evidence location.

The authorization continued to exclude inspection or configuration of the existing
unused Obsidian installation, real governed memory, real-data projection, network
or firewall changes, deployment, automatic refresh, runtime integration, and Stage
3 or later work.

## Stage 2 technical state

The exact host plan is recorded in
[`PHASE_8E_STAGE2_WINDOWS_PLAN.md`](../docs/PHASE_8E_STAGE2_WINDOWS_PLAN.md). The
dedicated account, protected sibling roots, source isolation, local AppLocker path
denies, verification, launcher foundation, rollback, and actual viewer-token test
harness are implemented. A same-volume move preserves the staging ACL, so every
successful export must be followed by:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\finalize-phase8e-projection.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\verify-phase8e-review-boundary.ps1 -RequireProjection
```

The finalizer is exact-pointer and containment bounded. A generation remains closed
to the viewer until finalization succeeds. Technical evidence is recorded in
[`ACC-0008`](../docs/acceptance/ACC-0008-phase8e-stage2-windows.md). Stage 2 is
Product Owner accepted. Application qualification is separately controlled below.

The Product Owner accepts unencrypted local storage as a physical-security risk
and prohibits installing, enabling, configuring, or deploying BitLocker on either
system. This removes BitLocker as a Phase 8E prerequisite but does not authorize
real-memory access, real-data generation, or any later-stage work.

## Stage 3 candidate test

The Product Owner authorized a narrow synthetic test of the existing per-user
Obsidian executable. The review account received temporary read-and-execute access
to only the Obsidian installation tree and a temporary outbound firewall block
scoped to that account. It read the synthetic projection and remained unable to
change it, but Obsidian did not remain running or register the synthetic vault.

The test failed closed and rollback passed. The original Obsidian permissions were
restored, the firewall rule and test-created review-profile state were removed, and
the executable remained unchanged. That original candidate is not qualified.
See [the Stage 3 test plan](../docs/PHASE_8E_STAGE3_OBSIDIAN_TEST_PLAN.md) and
[machine-readable evidence](evidence/stage3-obsidian-test-20260902.json).

## Stage 3 dedicated candidate

The Product Owner then authorized a separate copy of the same verified application
tree under the review profile. The dedicated executable retained its expected hash
and valid signature. It started under the real review token, registered the
synthetic projection as its vault, read all 25 notes, and remained unable to change
the immutable generation. Its exact viewer-only outbound rule blocked update checks.
The Product Owner account retained read access and its existing Obsidian installation
and settings remained unchanged.

The Product Owner accepted Stage 3 and authorized routine launch, commit, and push.
The exact fail-closed launcher was promoted and passed under the real review token;
no non-loopback connection was observed and the Product Owner's Obsidian remained
unchanged. Real-data generation and automatic refresh remain separately controlled.
See the
[dedicated plan](../docs/PHASE_8E_STAGE3_DEDICATED_OBSIDIAN_PLAN.md) and
[acceptance record](../docs/acceptance/ACC-0009-phase8e-stage3-obsidian.md).

PO-DEC-034 clarifies the central product purpose. G.R.A.C.I. must eventually learn
and reuse Product Owner-approved preferences, working methods, taught task
procedures, corrections, and lessons, and show that knowledge in the readable
Obsidian vault. The viewer remains read-only; a separate maintainer projects
accepted canonical memory into it. This direction does not authorize current real
personal data, ordinary learning or retrieval, vault-refresh integration, or
automatic updates.

PO-DEC-035 authorizes a separate Codex task to design and implement that foundation
with synthetic data only. Real personal information, deployment, automatic updates,
commit, and push remain outside that task's authority.
