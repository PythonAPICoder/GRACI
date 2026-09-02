# GRACI product

> Classification: current product identity and direction
> Authority: accepted Product Owner decisions, bounded by canonical governance
> Verified against: promoted Phase 8D commit `a0a61b7298d3c85cec054cd11ca827842f2776dd`
> Last verified: 2026-09-01

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
controlled cold-start validation failed because the active Windows Code Integrity
policy blocked an unsigned 3090 llama.cpp dependency. It is not cold-start or
Product Owner accepted, and no security-policy repair is authorized; see
[`ROADMAP.md`](ROADMAP.md).
