# Synthetic personalized-memory foundation

> Classification: Product Owner-accepted synthetic implementation foundation
> Authority: design and test description; canonical policy remains under `governance/`
> Designed against: `main` commit `8f9b0d3299107b265b872bd243b930961b655d3b`
> Prepared: 2026-09-02
> Status: PRODUCT OWNER ACCEPTED; SYNTHETIC ONLY; NOT DEPLOYED

## Outcome and boundary

This accepted foundation implements the synthetic behavior required by PO-DEC-034
without connecting it to the ordinary GRACI runtime. It supports proposals, exact
Product Owner approval attestations, durable creation, correction, retirement,
scoped retrieval, audit, technical rollback, and manual Phase 8E projection.

The following limits are enforced or preserved:

- A repository must carry an exact `SYNTHETIC_ONLY` boundary marker that denies
  real personal data, deployment, and automatic refresh.
- Every proposal and evidence reference must be labelled `synthetic:`. This is a
  development boundary, not proof that arbitrary text contains no personal data.
- A proposal may be stored without creating or changing canonical memory.
- Canonical creation, correction, retirement, and logical rollback require an
  exact Product Owner approval attestation from a typed turn or PTT release.
- Retrieved and projected content is always untrusted context. It cannot grant
  permission, change governance, expand scope, install a tool, promote code, or
  authorize an executable procedure.
- The ordinary operator, resident, controller, and PTT composition do not import
  this module. No running service, Windows control, Obsidian configuration, network
  rule, or deployed projection is changed.

The foundation does not inspect, infer, collect, or store real Product Owner data.
It does not create a general runtime authorization registry.

## Architecture

The foundation reuses two existing bounded systems:

1. Phase 4 memory supplies canonical validation, exact scope selection,
   supersession, expiry, conflict handling, and untrusted execution context rules.
2. Phase 8E supplies exact-commit repository reads, deterministic safe Markdown,
   immutable projection generations, manifests, tamper checks, and a read-only
   viewer boundary.

The new components are:

- [`graci/personalized_memory.py`](../graci/personalized_memory.py), an isolated
  synthetic repository and lifecycle service;
- personalized schema version 3 in [`graci/memory.py`](../graci/memory.py), which
  adds the memory kind and exact approval provenance to the existing governed
  fields; and
- [`phase8e/personalized_projection.py`](../phase8e/personalized_projection.py),
  a manual adapter that names one exact immutable synthetic generation for the
  existing projection exporter.

The data flow is:

```text
synthetic observation or direct request
              |
              v
typed proposal and proposal digest
              |
              | no canonical memory write
              v
exact Product Owner typed-turn or PTT approval attestation
              |
              v
new immutable state generation and audit event
              |
              +----> bounded scoped retrieval as untrusted context
              |
              +----> explicit exact-generation projection request
                             |
                             v
                    immutable Phase 8E vault generation
```

There is no path from Obsidian or projected Markdown back to canonical memory.

## Proposal and approval contract

A proposal names one action, personalized kind, exact scope, relevance key,
content, source turn, source boundary, evidence references, expiry, and, when
applicable, an exact target memory and version. Supported kinds are preference,
working method, task procedure, correction, and lesson.

The proposal digest covers every immutable proposal field. Approval must name that
proposal and digest exactly and must attest all of the following:

- decision `approve_exact`;
- authority `product_owner`;
- channel `typed_turn` or `ptt_release`; and
- the current source turn ID.

A missing, malformed, mismatched, stale, or already conflicting approval creates no
canonical memory change. Operation-derived IDs make exact retries idempotent while
rejecting reuse with different content.

This implementation does not authenticate the speaker or decide whether natural
language expressed approval. A later ordinary-runtime adapter must create the typed
attestation only after the existing trusted typed-turn or PTT-release boundary has
identified a direct Product Owner instruction. The model and memory content must
never be able to construct a trusted approval on their own.

## Durable state and audit

The synthetic repository uses complete immutable generations. Each generation
contains proposal records, canonical memory JSON, an ordered audit ledger, and a
hash manifest. The current pointer changes only after the complete generation has
been written and verified. A failed stage or current-pointer write leaves the prior
current generation unchanged.

Schema version 3 retains all governed schema version 2 fields and adds:

- `personalized_kind`; and
- `approval`, containing approval ID, proposal ID, Product Owner authority,
  submission channel, source turn, approval time, and proposal digest.

Audit events record proposal creation, approved creation, correction, retirement,
and rollback without copying memory content into the ledger. Every event has an
ordered sequence, trusted host timestamp, operation ID where applicable, and exact
object identifiers.

## Correction, retirement, conflict, and stale state

A correction proposal must name the active target version and preserve its scope,
relevance key, and personalized kind. Approval creates a new record, marks the
prior record superseded, and retains the explicit supersession edge. If another
approved change has already advanced or retired the target, the stale proposal
fails without mutation.

Retirement is the foundation's removal behavior. It tombstones the record so normal
retrieval excludes it while its approval and history remain reviewable. Physical
erasure and retention policy are intentionally not implemented because sensitive
real-data retention and deletion require a separate Product Owner decision.

Two active records at the same highest applicable scope, relevance key, and memory
type remain an explicit conflict. Retrieval returns no memory content for that
conflict. The projection labels every involved note `Reported` and does not choose
or merge a winner.

## Retrieval and authority isolation

Retrieval requires exact context, relevance keys, allowed personalized kinds, and
a bound. An optional expected generation ID prevents use of a newer or different
state than the caller reviewed. Scope composition, expiry, lifecycle exclusion,
specificity, and deterministic order reuse existing `MemoryGovernance` behavior.

Each result includes the source generation and manifest hash. Its evidence declares
the content `UNTRUSTED_CONTEXT_DATA` and lists the authority classes it cannot grant
or override. Conflict, corruption, invalid requests, and stale source expectations
fail closed.

This is a callable foundation API only. No model prompt, controller, resident turn,
or ordinary GRACI request currently invokes it.

## Projection and viewer behavior

The adapter requires one exact verified synthetic state generation. It names every
record in that generation, includes its already approved synthetic content, and
marks active conflicts. The Phase 8E exporter then validates schema version 3 and
renders approval provenance, lifecycle, content, and conflict state through the
existing inert Markdown path.

The adapter only builds a request. It does not run automatically, select a deployed
vault, finalize Windows ACLs, launch Obsidian, or refresh the accepted Stage 3
viewer. A future real-data maintainer must retain exact source selection and decide
content-bearing IDs under the separately approved privacy boundary.

## Failure handling and rollback

Technical transaction failure preserves the last-known-good current pointer. A
fully written but unselected orphan generation may remain for diagnosis. It is
never treated as current.

Logical rollback can restore proposal and memory state from a prior verified
generation, but it can also reactivate knowledge that was later corrected or
retired. It therefore requires a new exact Product Owner approval naming the target
generation and manifest hash. Rollback creates a new generation and appends an audit
event instead of moving the pointer backward or rewriting history.

No automatic generation deletion is implemented. Real-data retention, secure
erasure, orphan cleanup, backup, and restore remain later design decisions.

## Deterministic verification

Focused tests cover:

- exact approval and no canonical write from a proposal alone;
- typed-turn and PTT approval provenance;
- project scope isolation and untrusted authority labels;
- correction, retirement, conflict, expiry-compatible selection, and stale state;
- idempotent replay and operation conflicts;
- manifest tamper detection and failed-write preservation;
- hash-bound audited rollback;
- exact-generation projection, schema version 3 rendering, approval traceability,
  prompt-injection isolation, and visible conflicts; and
- continued absence from ordinary runtime imports.

The focused command is:

```powershell
python -W error -m unittest tests.test_personalized_memory tests.test_phase8e_personalized_projection tests.test_memory tests.test_memory_governance tests.test_memory_pipeline tests.test_phase4d tests.test_phase4e_acceptance tests.test_phase8e_projection tests.test_governance -v
```

Passing tests establish the named synthetic behavior only. They do not establish
deployment, runtime integration, or real-data safety. Product Owner acceptance and
promotion authority are recorded separately in PO-DEC-036 and ACC-0010.

## Open risks and next decision

The main security risk is the future adapter that translates a conversation into a
trusted approval attestation. It must be bound to the existing explicit turn and PTT
state, reject model-generated or replayed approval, present the exact proposed text
and scope to the Product Owner, and preserve evidence without recording unnecessary
personal data.

Other unresolved items are real-data root selection, privacy review, retention and
physical deletion, backup and restoration, ordinary relevance-key planning, prompt
composition, user-facing proposal review, maintainer identity and command surface,
manual vault-refresh promotion, and live acceptance.

The Product Owner accepted this synthetic foundation under PO-DEC-036 and
authorized commit and push. That acceptance does not authorize real personal data,
ordinary runtime integration, deployment, vault refresh, automatic updates, or
Phase 8F implementation. PO-DEC-037 subsequently superseded only that final Phase
8F restriction by authorizing a separate synthetic-only Stage 1 trusted secret
broker through Product Owner review. It did not authorize any integration with this
memory foundation, real personal data, deployment, automatic updates, or a later
Phase 8F stage.
