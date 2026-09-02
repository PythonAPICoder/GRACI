# G.R.A.C.I.

> Classification: concise repository entry point
> Current documentation: [`docs/INDEX.md`](docs/INDEX.md)
> Verified at commit: `dbc27123e0ab25a22ac1128677d2cd385de7d662`
> Last verified: 2026-09-01

**G.R.A.C.I.** means **General Reasoning And Conversational Intelligence**.
**Autonomous Assistant** is an approved descriptive subtitle/tagline, not part of
the acronym expansion.

GRACI is a local-first, governed assistant and development/runtime system. The RTX
3090 is authoritative and independently sufficient; the RTX 4090 is optional and
fail-closed under health, model, freshness, and exact MO2 policy. The Product Owner
is the final human authority.

Start every repository session with [`AGENTS.md`](AGENTS.md), then read
[`docs/INDEX.md`](docs/INDEX.md). Canonical policy is in
[`governance/CURRENT_POLICY.md`](governance/CURRENT_POLICY.md) and the stable
[`governance/POLICY_INDEX.md`](governance/POLICY_INDEX.md).

## Current product state

- Ordinary typed and resident/browser turns use one explicit governed local Qwen
  submission with strict schema validation and an independent user-facing response.
- Browser voice uses explicit PTT, local faster-whisper CPU STT, local Kokoro
  `af_heart` speech at speed `1.00`, and bounded browser-owned playback. PTT release
  is the spoken-turn submission boundary.
- Qwen/GLM routing, GLM review, governed memory, bounded autonomous repair, and
  optional 4090 execution are implemented specialized capabilities. They are not all
  composed into every ordinary conversational turn.
- The resident UI is loopback-only at `http://127.0.0.1:8766/` when running. It
  exposes observer state plus explicit bounded PTT, Restart, and speech
  claim/lifecycle controls.
- Telemetry agent 1.0.1 is observed deployed on the optional 4090. Full reboot,
  resource, and Product Owner acceptance is not yet established.
- The cold-start/runtime-readiness defect remains open.
- Phase 8D has not begun. System Health & Trusted Runtime Context is the leading
  proposed next objective, not authorized implementation work.

See the [capability matrix](docs/CAPABILITY_MATRIX.md),
[current status](CURRENT_STATUS.md), [current architecture](CURRENT_ARCHITECTURE.md),
and [known issues](docs/KNOWN_ISSUES.md) for the verified distinctions.

## Accepted UI baseline

Commit `dbc27123e0ab25a22ac1128677d2cd385de7d662` is the Product Owner physically
accepted current UI baseline: continuous voice-reactive outer ring, current subtitle,
Data Chatter Thinking Pulse, symmetric hardware HUD, and current voice/presence
presentation. Earlier 64-bar and right-status-rail designs are historical, not
restoration targets. See [`ACC-0001`](docs/acceptance/ACC-0001-phase8-ui-baseline.md).

## Local entry points

With the resident stopped, one explicit typed or speech turn can be run with:

```powershell
python -m graci "task"
python -m graci --speech
```

Optional flags include `--speak` for local speech and `--visualizer` for a temporary
loopback visualizer. The resident host owns the accepted browser-operator
composition when active; the one-shot CLI refuses to create a competing runtime.

Read-only operational checks and startup ownership are documented in
[`docs/OPERATIONS.md`](docs/OPERATIONS.md). Development and verification procedures
are in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

The complete warning-strict regression command is:

```powershell
python -W error -m unittest discover -s tests -v
```

Historical phase records remain under `phase*/` and are indexed by
[`docs/history/PHASE_INDEX.md`](docs/history/PHASE_INDEX.md). They preserve their
original truth but do not define current status or authorization.
