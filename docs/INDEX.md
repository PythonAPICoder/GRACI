# GRACI documentation index

> Classification: current documentation authority and navigation map
> Authority: accepted Product Owner documentation structure; policy authority remains in `governance/`
> Verified at commit: `dbc27123e0ab25a22ac1128677d2cd385de7d662`
> Last verified: 2026-09-01

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

At the start of a task, compare repository HEAD with each relevant current
document's `Verified at commit` value. If they differ, inspect the intervening diff
before treating the document as current. Live operational facts must include an
observation time; they are snapshots, not architectural promises.

Each durable fact should have one canonical home. Other documents link to it.
Historical records are preserved, current documents are reconciled rather than
appended indefinitely, and AI-generated summaries cannot promote themselves into
authority.
