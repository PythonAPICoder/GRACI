# GRACI documentation index

> Classification: current documentation authority and navigation map
> Authority: accepted Product Owner documentation structure; policy authority remains in `governance/`
> Verified through: PO-DEC-040 on 2026-09-03
> Last verified: 2026-09-03

This index is the durable starting point for reconstructing GRACI without
conversation history.

## Authority map

| Source | What it establishes | Precedence and limit |
|---|---|---|
| Current explicit Product Owner decision | Intent, acceptance, and authorization within its stated scope | Highest human authority; record durably before relying on it in a new session |
| [`governance/`](../governance/) | Canonical accepted policy and change control | Highest repository-level normative authority |
| Code and configuration | Implemented behavior at the checked commit | Cannot grant permission or prove deployment/acceptance |
| Deterministic tests | Mechanically verified cases | Passing tests do not prove deployment or physical acceptance |
| Current documents | Reconciled product, architecture, status, operations, issues, and roadmap | Must be checked against their `Verified at commit` value |
| Acceptance records | Exactly scoped automated, live, deployment, or Product Owner acceptance | Never generalize beyond the recorded scope |
| Historical phase records and evidence | What occurred or was accepted at a historical point | May contain facts later superseded; not current instructions |
| Conversation history and AI memory | Discovery context | Never authority; validate every claim independently |

If normative sources conflict, the latest explicit Product Owner decision and
accepted governance control, except that a stricter code-enforced safety boundary
remains effective until reconciled. If descriptive sources conflict, inspect Git,
code, configuration, tests, and time-stamped live evidence and report the conflict.

## Current reconstruction set

- [Product identity and intent](PRODUCT.md)
- [Current architecture](../CURRENT_ARCHITECTURE.md)
- [Current status](../CURRENT_STATUS.md)
- [Capability matrix](CAPABILITY_MATRIX.md)
- [Known issues](KNOWN_ISSUES.md)
- [Roadmap](ROADMAP.md)
- [Operations](OPERATIONS.md)
- [Development process](DEVELOPMENT.md)
- [Decision index](decisions/DECISION_INDEX.md)
- [Acceptance index](acceptance/ACCEPTANCE_INDEX.md)
- [Phase 8E personalized-memory acceptance](acceptance/ACC-0010-phase8e-personalized-memory.md)
- [Phase 8F Stage 1 acceptance](acceptance/ACC-0011-phase8f-stage1.md)
- [Phase 8F synthetic trusted secret broker](PHASE_8F_TRUSTED_SECRET_BROKER.md)
- [Phase 8E AppLocker incident](incidents/INC-0001-phase8e-stage2-applocker.md)
- [Phase 8E incident response authority](acceptance/ACC-0012-phase8e-incident-response.md)
- [Phase 8E AppLocker operational closure](acceptance/ACC-0013-phase8e-applocker-operational-closure.md)
- [Completed Phase 8E read-only host audit](PHASE_8E_READ_ONLY_HOST_AUDIT_PLAN.md)

## Design proposals

- [Phase 8E replacement viewer-boundary design](PHASE_8E_REPLACEMENT_BOUNDARY_DESIGN.md)
  is approved for design only and replaces AppLocker with narrower identity,
  filesystem, inert-content, manifest, immutable-generation, and launcher controls.
- [Phase 8F Stage 1 synthetic trusted secret broker](PHASE_8F_TRUSTED_SECRET_BROKER.md)
  documents the accepted isolated authenticated-encryption, exact capability
  grant, operation-only adapter, audit, recovery, rollback, and adversarial-test
  foundation. Acceptance is recorded in
  [ACC-0011](acceptance/ACC-0011-phase8f-stage1.md). It is not deployed and is not
  authorized for real credentials, live IPC, Windows configuration, ordinary
  runtime use, or later Phase 8F work.
- [Synthetic personalized-memory foundation](PERSONALIZED_MEMORY_FOUNDATION.md)
  describes the Product Owner-accepted proposal, exact approval, lifecycle, scoped
  retrieval, audit, rollback, and manual Phase 8E projection foundation. It uses
  synthetic fixtures only and is not deployed.
- [Phase 8E Obsidian knowledge and governance review foundation](PHASE_8E_OBSIDIAN_DESIGN.md)
  retains the accepted one-way projection and human-view direction. Its fixture-only
  Stage 1 implementation is documented in the
  [Phase 8E Stage 1 record](../phase8e/README.md) and accepted in
  [ACC-0007](acceptance/ACC-0007-phase8e-stage1.md). The former Stage 2 Windows
  boundary is rejected; [ACC-0008](acceptance/ACC-0008-phase8e-stage2-windows.md)
  and its [exact plan](PHASE_8E_STAGE2_WINDOWS_PLAN.md) are historical evidence.
  Obsidian
  qualification began with a [bounded Stage 3 candidate test](PHASE_8E_STAGE3_OBSIDIAN_TEST_PLAN.md);
  the existing per-user candidate failed closed and rollback passed. The
  [dedicated review-profile candidate](PHASE_8E_STAGE3_DEDICATED_OBSIDIAN_PLAN.md)
  then passed its synthetic test. Stage 3 application qualification is historical,
  and its dependent routine launch is withdrawn in
  [ACC-0012](acceptance/ACC-0012-phase8e-incident-response.md).
  `PO-DEC-034` clarifies the central future purpose: approved personal preferences,
  working methods, taught tasks, corrections, and lessons must be readable in the
  vault and reusable by G.R.A.C.I. Real personal data, learning and retrieval,
  automatic refresh, and later stages remain separately controlled.

## Governance

- [Current policy](../governance/CURRENT_POLICY.md)
- [Policy index](../governance/POLICY_INDEX.md)
- [Governance change process](../governance/CHANGE_PROCESS.md)

Current documents summarize policy only when needed for comprehension and link to
the canonical policy instead of creating competing rules.

## Historical and context material

- [Phase index](history/PHASE_INDEX.md)
- [Legacy-document register](history/LEGACY_DOCUMENTS.md)
- [`PROJECT_STATE.md`](../PROJECT_STATE.md) is a legacy chronological record.
- Phase READMEs, logs, and evidence remain truthful historical records.
- The former `codex-memory-bootstrap/` temporary migration package was removed with
  Product Owner authorization after the durable repository-memory foundation passed
  a fresh-session reconstruction test and was accepted.

## Freshness rule

At the start of a task, compare repository HEAD and current authority with each
relevant document's freshness marker. If they differ, inspect the intervening diff
before treating the document as current. Live operational facts must include an
observation time; they are snapshots, not architectural promises.

Each durable fact should have one canonical home. Other documents link to it.
Historical records are preserved, current documents are reconciled rather than
appended indefinitely, and AI-generated summaries cannot promote themselves into
authority.
