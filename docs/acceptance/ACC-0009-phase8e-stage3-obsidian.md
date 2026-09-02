# ACC-0009: Phase 8E Stage 3 dedicated Obsidian

> Classification: durable automated, live validation, deployment, and acceptance record
> State: PRODUCT OWNER ACCEPTED
> Recorded: 2026-09-02

## Accepted scope

The Product Owner accepted Phase 8E Stage 3 and authorized routine launch, commit,
and push to `main`. The accepted application is the dedicated Obsidian 1.13.4 copy
at `C:\Users\GRACI_Review\AppData\Local\Programs\Obsidian\Obsidian.exe`, SHA-256
`c01bbd79583037639f5422396cddb457ef48e89e159ca50a8492bbd1f1f10775`, with a valid
Dynalist Inc signature.

The dedicated application is available to the exact `GRACI_Review` SID and is
covered by an outbound firewall block scoped only to that SID and executable. The
Product Owner account retains read access to the vault. The Product Owner's personal
Obsidian installation and settings remain separate and unchanged.

## Verification and deployment

The first candidate based on the Product Owner's per-user installation failed closed
and was fully rolled back. The separately installed review-profile copy then passed
the real-token synthetic test. It registered `E:\GRACI-Review-Projection`, read all
25 synthetic notes, could not change the immutable generation, and produced no
observed non-loopback established connection.

After acceptance, the exact fail-closed launcher and qualification record were
promoted. A fresh routine launch under the real review token passed application,
signature, hash, viewer identity, firewall, manifest, output hash, vault registration,
and plugin-policy checks. The application remained running for the bounded test
interval. Resident HTTP health remained 200, and the Product Owner's Obsidian was not
stopped. Exact rollback procedures exist for the launcher promotion and dedicated
installation.

Machine-readable records are
[`stage3-dedicated-obsidian-20260902.json`](../../phase8e/evidence/stage3-dedicated-obsidian-20260902.json)
and [`stage3-routine-launch-20260902.json`](../../phase8e/evidence/stage3-routine-launch-20260902.json).

## Authority boundary

All viewed content remains synthetic. This acceptance does not authorize real
governed memory, a real-data projection, automatic refresh, ordinary runtime
integration, Stage 4 or later work, plugins, external/cloud assistance, or any
BitLocker installation or configuration. Obsidian remains an optional human view,
not a source of truth and not a permission source.
