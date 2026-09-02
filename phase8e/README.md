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

The authorization continues to exclude Obsidian installation and application
settings, real governed memory, real-data projection, network or firewall changes,
deployment, automatic refresh, runtime integration, and Stage 3 or later work.
