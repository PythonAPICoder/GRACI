# Phase 5E — Visualizer Acceptance & Closure

Phase 5 is complete. The accepted stack is an optional, local, observer-only view
of authoritative GRACI runtime facts. It does not submit work or participate in
execution. Phase 6 — Voice is next and has not begun.

## Reconstructible architecture

1. `graci.visualizer` defines frozen versioned snapshots and events, deterministic
   JSON serialization, the pure trusted-state projector, bounded metadata, and the
   100-event ordered append-only buffer. Supported states are `idle`, `listening`,
   `planning`, `retrieving_memory`, `reasoning`, `executing_tool`, `testing`,
   `reviewing`, `adjudicating`, `completed`, `warning`, `failed`, and `speaking`.
   LISTENING and SPEAKING are reserved for Phase 6.
2. `graci.visualizer_backend` is an optional standard-library server fixed to
   `127.0.0.1:8766`. GET and HEAD are accepted for `/graci/visualizer/v1/health`,
   `/snapshot`, `/events`, and `/events/stream`; only the packaged root, CSS, and
   JavaScript assets are also served. There is no CORS, upload, control, mutation,
   shutdown, arbitrary-path, or remote binding surface. SSE retains 100 events and
   permits at most eight clients.
3. `graci.visualizer_ui` is offline HTML/CSS/vanilla JavaScript/SVG. It requires no
   CDN, font, analytics, cloud, or external asset. The accepted layouts are
   3440x1440, 2560x1440, and 1920x1080. The orbital geometry animates when motion is
   enabled while center labels remain stationary; `prefers-reduced-motion` removes
   continuous animation. Disconnect marks the last snapshot stale and never invents
   a GRACI failure.
4. `graci.observation` is the sole optional core-facing API. It is a no-op without an
   observer and contains observer exceptions. `graci.visualizer_runtime` maps trusted
   lifecycle facts into the Phase 5A projection and publishes in process. Core code
   does not import the backend or UI, and browser/backend absence cannot change task,
   inference, routing, tool, test, memory, review, adjudication, or terminal results.

## Accepted representation and privacy boundary

The 3090 is primary authority and independently sufficient. The 4090 is optional
capacity only; the display reflects existing Phase 3 eligibility, MO2 status,
endpoint health, selected node, and fallback without probing or controlling them.
Qwen implementer identity is exactly `qwen3.8-27b-q4_k_m`; GLM reviewer identity is
exactly `GLM-4.7-Flash-64x2.6B-Q4_K_M`. REVIEWING and deterministic ADJUDICATING are
separate. The accepted GLM path used deterministic Phase 3B integration because
loading an otherwise unloaded reviewer was unnecessary.

Memory projection is metadata-only: mode, relevance keys, selected and supplied IDs
and counts, context size, conflicts, corruptions, and status. It never contains memory
content, raw vault data, prompt envelopes, or private files. Tool and test projection
uses real lifecycle boundaries with bounded target/category/status/error facts and no
raw stdout or stderr. Prompts, secrets, environment data, hidden reasoning, and
chain-of-thought are excluded from every public contract.

## Final acceptance

The real local acceptance on 2026-08-28 used only
`http://127.0.0.1:8080/v1`, server-reported model
`qwen3.8-27b-q4_k_m`, and node `3090-primary-localhost`. It truthfully traversed
PLANNING, RETRIEVING_MEMORY, REASONING, TESTING, and COMPLETED; deterministic tests
passed and the terminal reason was `tests_passed`. Deterministic integration also
covers real tool activity, governed Phase 4 memory metadata, warning and failure,
distinct review/adjudication, optional 4090/MO2 representation, observer absence,
observer exceptions, and reconstruction in fresh processes.

Browser acceptance found no horizontal overflow or console errors at all three target
resolutions. An isolated backend termination changed the UI to DISCONNECTED and
STALE while retaining the last speaking snapshot; it did not set FAILED. Static
validation passed warning-strict Python compilation, JavaScript syntax, evidence JSON
parsing, bounded secret and external-reference scans, UI/path security inspection,
and `git diff --check`.

Focused Phase 5 acceptance passes 66 tests and the complete warning-strict repository
suite passes 254 tests. No Phase 5 defect was discovered during Phase 5E.

## Accepted limitations

- The browser visualizer is localhost-only and strictly observational.
- LISTENING and SPEAKING remain reserved until Phase 6.
- Live GLM loading was omitted; deterministic accepted integration covers its path.
- The 4090, shared drive, Obsidian, and cloud are not required.
- Advanced appearance and presence refinement remains reserved for Phase 8.

Evidence is `phase5e/evidence/phase5e-closure.json`. No Phase 6 microphone, speech,
TTS, wake-word, voice-selection, or control work is included.
