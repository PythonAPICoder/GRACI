# ACC-0010: Phase 8E synthetic personalized-memory foundation

> Classification: durable synthetic implementation, verification, and acceptance record
> State: PRODUCT OWNER ACCEPTED
> Recorded: 2026-09-02

## Accepted scope

The Product Owner accepted the Phase 8E synthetic personalized-memory foundation
and authorized recording the acceptance, committing the accepted changes, and
pushing them to `main`.

The accepted foundation provides an isolated synthetic repository for proposals,
exact typed-turn or PTT approval attestations, schema-version-3 approval
provenance, immutable state and audit generations, correction, retirement,
conflict and stale-state handling, scoped retrieval, hash-bound rollback, and an
exact-generation adapter for the existing Phase 8E projection exporter.

The foundation remains outside ordinary GRACI composition. It does not inspect,
infer, collect, or store real Product Owner data. Retrieved and projected content
remains untrusted context and cannot grant authority, change governance, expand
scope, install tools, promote code, or authorize executable actions.

## Verification

The final focused warning-strict regression covered the personalized-memory and
projection tests together with the affected Phase 4 memory, Phase 8E projection,
and governance suites. All 133 tests passed.

A final resident-safe warning-strict broad regression selected 603 tests and all
passed. It excluded the three one-shot CLI modules that require the resident host
to be inactive. The resident remained active and unchanged because this task did
not authorize stopping it. A full-discovery attempt was not accepted as canonical
evidence because 24 expected one-shot cases were rejected by the active resident
lock. Compilation, documentation-link validation, and `git diff --check` also
passed.

The broad regression created four ignored synthetic records under `runs/`. They
were identified against the pre-test snapshot and removed precisely. No
pre-existing run record or Product Owner data was changed.

## Authority boundary

This acceptance authorizes only preservation of the synthetic foundation through
the authorized repository commit and push. It does not authorize real personal
data, ordinary runtime integration, deployment, automatic vault refresh, automatic
updates, external or cloud assistance, BitLocker changes, or Phase 8F
implementation.

Future work involving trusted conversational approval, real-data storage,
retrieval in ordinary tasks, vault maintenance, credentials, a security broker,
standing grants, or autonomous actions requires a separate explicit Product Owner
decision.
