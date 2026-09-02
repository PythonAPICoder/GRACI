# Phase 8E Stage 3 dedicated Obsidian plan

> Classification: pre-mutation implementation plan
> Authority: Product Owner authorization, 2026-09-02
> Baseline: `b57662a1373990a2953540209f3a901770ebc0b7`
> State: PRODUCT OWNER ACCEPTED; ROUTINE LAUNCH PROMOTED

## Plain-language goal

Install a separate local copy of the already verified Obsidian application for
`AI-SERVER\GRACI_Review`. Use only the existing synthetic review files for the
first test. Keep the Product Owner's Obsidian installation and settings unchanged,
and preserve the Product Owner's ability to read the review vault.

No download is required. No BitLocker or other encryption change is permitted.

## Exact changes

- Copy the verified application tree from
  `C:\Users\Steve\AppData\Local\Programs\Obsidian` to the review profile's exact
  `AppData\Local\Programs\Obsidian` directory.
- Protect that copy so the review account can run it but cannot alter its program
  files. SYSTEM, Administrators, and the Product Owner retain full control.
- Treat `E:\GRACI-Review-Projection` as the synthetic Obsidian vault. Create only
  its `.obsidian` settings directory as viewer-writable; the generated review
  notes remain read-only.
- Create only the review account's Obsidian settings. Do not inspect or alter the
  Product Owner's Obsidian settings.
- Add one outbound firewall block applying only to the exact dedicated executable
  and the exact review-account SID.
- Run a bounded synthetic test as the real review account. Verify application
  start, note readability, write denial outside `.obsidian`, unchanged generated
  notes, registered vault, no observed non-loopback connection, and Product Owner
  read access.

## Failure and rollback

Any unexpected existing destination, path mismatch, reparse point, source mismatch,
copy mismatch, permission mismatch, firewall mismatch, or failed synthetic test
fails closed. Rollback removes only the newly created dedicated application,
review-account Obsidian state, vault `.obsidian` directory, exact firewall rule,
and copied test worker. It preserves evidence and does not touch the Product
Owner's Obsidian installation or settings.

Success leaves the dedicated copy, viewer-only firewall rule, and synthetic vault
configuration in place for Product Owner inspection. It does not authorize real
memory, automatic refresh, plugins, cloud access, or BitLocker changes.

## Observed result

The exact verified Obsidian 1.13.4 tree was copied to the review profile. The
dedicated executable retained its expected SHA-256 hash and valid Dynalist signature.
The real review token started Obsidian, read all 25 synthetic Markdown notes,
registered `E:\GRACI-Review-Projection` as its vault, and remained unable to write
inside the immutable generation. Protected projection files were unchanged.

Obsidian attempted its normal update checks. The exact viewer-only firewall rule
blocked those requests, and no non-loopback established connection was observed.
An initial UTF-8 byte-order mark in the two JSON settings files produced a parse
warning. The files were rewritten as UTF-8 without a byte-order mark and the full
synthetic test then passed without a configuration parse error.

The Product Owner's normal account successfully read all 25 notes and the vault
settings. The Product Owner's existing Obsidian executable hash and settings-folder
timestamp remained unchanged. The accepted Stage 2 verifier passed, the resident
GRACI page returned HTTP 200, and no Obsidian process was left running after the
test.

The Product Owner then accepted Stage 3 and authorized routine launch, commit, and
push. The exact launcher and qualification record were promoted. A fresh launch
under the real review token passed all boundary and application checks, left the
dedicated application running for the bounded observation interval, established no
non-loopback connection, and left resident HTTP health at 200. The Product Owner's
personal Obsidian was not stopped or changed. Real data, automatic refresh, runtime
integration, and Stage 4 remain unauthorized.
