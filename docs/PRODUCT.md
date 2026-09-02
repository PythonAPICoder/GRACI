# GRACI product

> Classification: current product identity and direction
> Authority: accepted Product Owner decisions, bounded by canonical governance
> Verified through: PO-DEC-035 after Phase 8E Stage 3 acceptance on 2026-09-02
> Last verified: 2026-09-02

## Identity

**G.R.A.C.I.** means **General Reasoning And Conversational Intelligence**.

**Autonomous Assistant** is an approved descriptive subtitle/tagline. It is not
part of the acronym expansion. GRACI is the product identity; Qwen, GLM, Codex, and
other AI components are subordinate implementation or advisory components.

The Product Owner is the final human authority. Current authority, autonomy,
compute, model, memory, voice, external-assistance, and validation policy is
canonical in [`governance/CURRENT_POLICY.md`](../governance/CURRENT_POLICY.md).

## Product direction

GRACI is a local-first assistant and governed development/runtime system. The
primary RTX 3090 must remain independently sufficient. The optional RTX 4090 may
provide enhanced capacity only when current health and MO2 policy allow it.

The long-term ordinary runtime should select appropriate capabilities according to
the task, policy, latency, resource availability, cost, and verification need. That
direction does not require every turn to invoke routing, review, memory, optional
compute, repair, and verification indiscriminately, and it does not authorize a
runtime redesign by itself.

The central purpose of the accepted Obsidian design is to make GRACI's long-term
knowledge readable to the Product Owner and useful to GRACI. That knowledge includes
the Product Owner's preferences, working methods, task procedures taught directly or
learned through approved and verified work, confirmed corrections, and lessons,
alongside governance, decisions, status, and
acceptance evidence. A new or changed durable memory requires explicit current
Product Owner approval, including a direct verbal or PTT instruction to remember it.
Once approved, GRACI should retrieve and use that knowledge during later relevant
work without requiring the Product Owner to teach it again. A separate maintainer
updates the readable vault while the Obsidian viewer remains read-only. Vault text
cannot grant permissions, change governance, or silently authorize tools, code, or
actions. Ordinary learning, retrieval, and real-data vault refresh are not yet
implemented.

Another future product capability is permission-gated internet research. When
approved local capabilities cannot complete an authorized task, GRACI
will support permission-gated internet research. A knowledge gap will produce a
sourced, locally reviewed answer; a missing tool will enter isolated tool
qualification. GRACI will normally compare about three credible candidates, test and
grade them, and seek separate Product Owner approval before installing or using a
selected tool in production. These are required product objectives, not current
runtime authority.

GRACI must also be able to create bounded Model Context Protocol (MCP) integrations
or, with applicable permission, locate and qualify existing MCPs through the same
sandboxed tool-adoption process. Production connection remains a separate Product
Owner decision.

A required local document-ingestion capability will safely extract approved files,
including PDF résumés, before a local-first RAG capability retrieves relevant
knowledge with source traceability. Canonical documents and governed memory remain
distinct from derived indexes. A required corrective-learning loop will record
confirmed mistakes, Product Owner corrections, jointly verified repairs, and lessons
learned, then retrieve applicable accepted lessons during similar future work. This
learning is governed memory and retrieval, not silent model retraining, authority
expansion, or autonomous self-promotion.

GRACI also requires scheduled proactive work under explicit standing Product Owner
grants. A named recurring task may run at its approved cadence without a new prompt
each time, but it cannot broaden its purpose, data use, external access, actions, or
duration. A daily résumé-based job search may find, deduplicate, rank, and report
public openings; applying, disclosing the résumé, contacting an employer, creating
an account, or spending money remains separately permissioned.

All human-facing documents created by GRACI must use natural, audience-appropriate
professional writing. New prose must avoid em dash punctuation, double-hyphen
substitutes, canned AI phrasing, repetitive summaries, excessive formatting, vague
filler, fabricated claims, and false authorship statements. Document workflows must
also perform the proofreading and format-specific visual or structural checks needed
for a finished human-quality artifact.

The complete-assistant direction also requires unified planning, a clear permission
center and approval inbox, secure credential storage, governed everyday-service
connectors, safe browser and desktop action, multimodal understanding and media
workflows, tested backup and recovery, and measurable task outcomes. These
capabilities must make GRACI easier to use without weakening local-first operation,
Product Owner control, evidence, or rollback.

Interaction is currently explicit: typed input or push-to-talk. PTT release is the
spoken-turn submission boundary. There is no authorized wake word, VAD authority,
always-listening mode, or autonomous follow-up.

## Accepted presentation baseline

Commit `dbc27123e0ab25a22ac1128677d2cd385de7d662` is the Product Owner physically
accepted current UI baseline. It includes:

- the continuous voice-reactive outer ring;
- the current identity subtitle;
- the Data Chatter Thinking Pulse;
- the symmetric hardware HUD; and
- the current voice and presence presentation.

Earlier 64-bar speech visualizations, the permanent right status rail, and other
superseded visual experiments are historical, not restoration targets. The durable
scope is recorded in
[`ACC-0001-phase8-ui-baseline.md`](acceptance/ACC-0001-phase8-ui-baseline.md).

Production speech uses local Kokoro `af_heart` at speed `1.00`, with `GRACI`
pronounced `GRAY-see`. This supersedes the historical Phase 6 `af_bella` selection;
historical qualification evidence remains unchanged.

## Current boundary

The development-process handoff and durable repository-memory foundation are Product
Owner accepted. The temporary bootstrap migration package has been removed. Phase 8D
System Health & Trusted Runtime Context is promoted and deployed at `a0a61b7`. Its
first controlled cold-start validation exposed an active Windows Code Integrity
block in the 3090 llama.cpp build. An explicitly authorized security-preserving
replacement and repeat procedure now provide a passing five-minute automated
cold-start record without weakening Code Integrity. The Product Owner explicitly
accepted Phase 8D on 2026-09-01.

The Product Owner separately authorized bounded inspection, upgrade, deployment,
rollback verification, and acceptance work for the optional 4090 llama.cpp runtime;
see [`ROADMAP.md`](ROADMAP.md).
