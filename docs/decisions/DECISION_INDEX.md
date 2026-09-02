# GRACI decision index

> Classification: current accepted Product Owner decision register
> Authority: accepted Product Owner decisions; canonical policy remains under `governance/`
> Verified against: promoted Phase 8D commit `a0a61b7298d3c85cec054cd11ca827842f2776dd`
> Last verified: 2026-09-01

Only decisions with durable value beyond an implementation detail belong here.
Individual decision files are created only when rationale, alternatives, or
consequences require more space.

| ID | Accepted decision | Durable expression |
|---|---|---|
| PO-DEC-001 | The canonical acronym is **General Reasoning And Conversational Intelligence**. “Autonomous Assistant” is an approved subtitle/tagline, not acronym text. | [`PRODUCT.md`](../PRODUCT.md), `QA-006`, current UI |
| PO-DEC-002 | Production speech is local Kokoro `af_heart` at speed `1.00`; it supersedes historical `af_bella` without rewriting historical evidence. | [`PRODUCT.md`](../PRODUCT.md), [`CURRENT_POLICY.md`](../../governance/CURRENT_POLICY.md#voice-and-conversational-policy) |
| PO-DEC-003 | Future ordinary runtime composition should select routing, review, memory, optional compute, repair/recovery, and verification according to task, policy, latency, resources, and verification need—not invoke every subsystem blindly. This is direction, not redesign authorization. | [`PRODUCT.md`](../PRODUCT.md), [`CAPABILITY_MATRIX.md`](../CAPABILITY_MATRIX.md), [`ROADMAP.md`](../ROADMAP.md) |
| PO-DEC-004 | Shared storage is optional infrastructure and never authoritative GRACI storage. The repository and canonical local data remain on the 3090. | [`OPERATIONS.md`](../OPERATIONS.md), memory policy |
| PO-DEC-005 | Phase 8D had not begun and was initially only the leading proposed objective. **Superseded by PO-DEC-008.** | [`ROADMAP.md`](../ROADMAP.md) |
| PO-DEC-006 | The ChatGPT bootstrap package was temporary **CONTEXT ONLY** migration material. Remove it after the durable repository-memory foundation passes its fresh-session reconstruction test and is accepted. | [`ACC-0002`](../acceptance/ACC-0002-memory-foundation.md), [`LEGACY_DOCUMENTS.md`](../history/LEGACY_DOCUMENTS.md) |
| PO-DEC-007 | The durable repository-memory/documentation foundation is accepted after a fresh Codex session reconstructed GRACI's current state using only the repository. This acceptance does not authorize Phase 8D. | [`ACC-0002`](../acceptance/ACC-0002-memory-foundation.md), [`ROADMAP.md`](../ROADMAP.md) |
| PO-DEC-008 | Phase 8D System Health & Trusted Runtime Context is authorized within the bounded read-only scope documented in the roadmap. Implementation does not authorize deployment, reboot testing, issue closure, Product Owner acceptance, autonomous repair, new routing, cloud use, wake/VAD, or always-listening behavior. | [`ROADMAP.md`](../ROADMAP.md), [`KNOWN_ISSUES.md`](../KNOWN_ISSUES.md) |
| PO-DEC-009 | Promote/deploy the verified Phase 8D implementation and execute a separate controlled cold-start acceptance procedure. This authorizes the named promotion, deployment, and evidence run; it does not authorize weakening Code Integrity, trusting unsigned code, autonomous repair, issue closure, or Product Owner acceptance by implication. | [`ACC-0003`](../acceptance/ACC-0003-phase8d-cold-start.md), [`ROADMAP.md`](../ROADMAP.md) |

The accepted UI baseline is an acceptance event rather than a general architecture
decision; see [`ACC-0001`](../acceptance/ACC-0001-phase8-ui-baseline.md). The
cold-start defect and telemetry acceptance gap are maintained in
[`KNOWN_ISSUES.md`](../KNOWN_ISSUES.md), where their open status and closure evidence
can be tracked without inventing a decision.
