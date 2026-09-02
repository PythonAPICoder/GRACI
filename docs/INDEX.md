# GRACI documentation index

> Classification: current documentation authority and navigation map
> Authority: accepted Product Owner documentation structure; policy authority remains in `governance/`
> Verified through: Phase 8E Stage 3 Product Owner acceptance and routine-launch promotion
> Last verified: 2026-09-02

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

## Design proposals

- [Phase 8E read-only Obsidian knowledge and governance review](PHASE_8E_OBSIDIAN_DESIGN.md)
  is the Product Owner-accepted design. Its fixture-only Stage 1 implementation is
  documented in the [Phase 8E Stage 1 record](../phase8e/README.md) and accepted in
  [ACC-0007](acceptance/ACC-0007-phase8e-stage1.md). Stage 2 local Windows boundary
  work is accepted in [ACC-0008](acceptance/ACC-0008-phase8e-stage2-windows.md)
  and documented in its [exact plan](PHASE_8E_STAGE2_WINDOWS_PLAN.md). Obsidian
  qualification began with a [bounded Stage 3 candidate test](PHASE_8E_STAGE3_OBSIDIAN_TEST_PLAN.md);
  the existing per-user candidate failed closed and rollback passed. The
  [dedicated review-profile candidate](PHASE_8E_STAGE3_DEDICATED_OBSIDIAN_PLAN.md)
  then passed its synthetic test. Stage 3 acceptance and routine-launch promotion
  are recorded in [ACC-0009](acceptance/ACC-0009-phase8e-stage3-obsidian.md). Real
  data, automatic refresh, and later stages remain separately controlled.

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
