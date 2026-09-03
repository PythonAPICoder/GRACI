# ACC-0011: Phase 8F Stage 1 synthetic trusted secret broker

> Classification: durable synthetic implementation, verification, and acceptance record
> State: PRODUCT OWNER ACCEPTED
> Recorded: 2026-09-02

## Accepted scope

The Product Owner accepted the Phase 8F Stage 1 synthetic trusted secret broker
and capability-grant foundation and authorized recording the acceptance,
committing the reviewed changes, and pushing them to `main`.

The accepted foundation is the isolated `phase8f` package described by
[`PHASE_8F_TRUSTED_SECRET_BROKER.md`](../PHASE_8F_TRUSTED_SECRET_BROKER.md). It
implements Windows CNG AES-256-GCM with injected synthetic keys, authenticated
metadata envelopes, opaque secret references, exact Product Owner approval
records, one-time and bounded standing grants, expiry, review, revocation,
persistent pre-dispatch reservation, replay control, sanitized operation results,
hash-chained audit, recovery, rollback, and one fake operation-specific adapter.

The package remains outside ordinary G.R.A.C.I. composition. It has no general
raw-secret retrieval interface, production identity, durable production key,
live IPC, external connector, or deployment path. Stage 1 used only generated
synthetic values and fake destinations.

## Verification

The focused warning-strict Phase 8F suite passed all 52 tests. Independent
architecture and adversarial review found no remaining P0/P1 or material P2 issue.

The final canonical warning-strict repository command passed all 684 tests:

```powershell
python -W error -m unittest discover -s tests -v
```

An immediately preceding broad run encountered one unrelated transient Windows
`WinError 5` while a Phase 1 test renamed a temporary evidence file. The isolated
test then passed, and the complete 684-test command passed on its immediate rerun.
`git diff --check`, compilation, governance-link validation, and the staged-file
inspection also passed.

The two broad runs created eight ignored synthetic records under `runs/`. The
directory was empty before testing. All eight generated records were identified
exactly and removed, leaving the directory empty. No pre-existing record or Product
Owner data was changed. Tests checked generated secret sentinels through boolean
absence assertions and did not print synthetic secret values into evidence.

## Authority boundary

This acceptance authorizes only preservation of the reviewed Stage 1 foundation
through the authorized repository commit and push. It does not authorize real
credentials or personal data; production identity or key custody; Windows account,
certificate, TPM, ACL, service, firewall, or network changes; live IPC; external or
cloud access; connector qualification; deployment; automatic refresh; ordinary
runtime integration; model, memory, Obsidian, resident, controller, 3090, or 4090
changes; or any later Phase 8F stage.

Production identity, protected durable key custody, authenticated local transport,
ACL and service isolation, backup and restore, external anti-rollback protection,
connector contracts, real-data handling, deployment, and later Phase 8F work remain
separate Product Owner decisions. No such work may begin by implication from this
acceptance.
