# Phase 8F Stage 1: synthetic trusted secret broker

This package implements the PO-DEC-037 synthetic-only foundation for brokered
secret use and exact capability grants. It is intentionally separate from the
`graci` package and ordinary operator, controller, resident, model, memory, and
Obsidian composition.

The four implementation modules provide:

- Windows CNG AES-256-GCM with injected ephemeral test keys and mutable redacted
  plaintext buffers;
- canonical authenticated metadata envelopes with exact caller, grant, generation,
  scope, resource, operation, destination, opaque reference, freshness, and replay
  binding;
- an immutable-generation encrypted store with exact Product Owner approval
  records, one-time and bounded standing grants, expiry, review, revocation,
  persistent pre-dispatch reservation, a dispatch-to-completion store-lock fence,
  audit, uncertain-outcome closure, and hash-bound secret rollback; and
- one fixed fake notice adapter with no network, service, filesystem, subprocess,
  model, memory, resident, or other external side effect.

No public raw-secret read or export operation exists. Tests generate synthetic
values at runtime and check that plaintext does not appear in protocol messages,
metadata, results, exceptions, representations, or stored evidence. Best-effort
buffer clearing cannot guarantee erasure of copies retained by Python, native
libraries, or the operating system.

Initialize a new store at an absolute path on a fixed local Windows volume that does
not yet exist. Mapped network, removable, optical, RAM-disk, unknown, and invalid
drive types fail closed. A fully verified sibling staging tree is published with a
Windows write-through move.
Opening an existing store uses `SyntheticSecretBroker(...)` with the same injected
synthetic keys and exact adapter registration. Key persistence and restart recovery
are intentionally not implemented.

Run the focused verification with:

```powershell
python -W error -m unittest tests.test_phase8f_crypto tests.test_phase8f_protocol tests.test_phase8f_synthetic_adapter tests.test_phase8f_broker -v
```

Passing tests establish only the isolated synthetic behavior. The Product Owner
accepted Stage 1 for repository preservation under PO-DEC-038. It is not deployed
and does not authorize real credentials or personal data, production identity or
key custody, Windows configuration, live IPC, network access, external services,
ordinary runtime integration, or a later Phase 8F stage. See
[`ACC-0011`](../docs/acceptance/ACC-0011-phase8f-stage1.md) and
[`PHASE_8F_TRUSTED_SECRET_BROKER.md`](../docs/PHASE_8F_TRUSTED_SECRET_BROKER.md).
