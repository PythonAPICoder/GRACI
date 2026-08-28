# Phase 5C — Command-Center UI

Phase 5C adds G.R.A.C.I.'s first browser identity as a same-origin, read-only command center at `http://127.0.0.1:8766/`. It is ultrawide-first (3440x1440), works offline, and uses only packaged HTML, CSS, JavaScript, and SVG. There is no Node runtime, build pipeline, framework, external font, CDN, analytics, or remote asset. API v1 and Phase 5A schemas are unchanged.

## Architecture and assets

- `graci/visualizer_ui/index.html` is semantic observer-only markup.
- `graci/visualizer_ui/visualizer.css` owns responsive visuals and the comprehensive `prefers-reduced-motion` override.
- `graci/visualizer_ui/visualizer.js` fetches health/snapshot/events, opens SSE, deduplicates IDs, caps rendered events at 100, and refreshes snapshots every 3000 ms. Malformed events are ignored.
- `graci.visualizer_backend` serves only those three allowlisted assets from a fixed package directory. It rejects decoded traversal, has no directory listing, bounds assets to 512 KB, fixes MIME types, and adds restrictive CSP while retaining GET/HEAD-only behavior.
- `phase5c.synthetic.lifecycle` constructs immutable visual fixtures. It cannot publish over HTTP and has no backend or core-runtime dependency. `python -m phase5c.run_visual_demo --hold reasoning` hosts it internally.

## Visual system

The primary layout is compute/agents, central SVG core, and current activity. A horizontal memory → Qwen → tools → tests → GLM review → deterministic adjudication pipeline and bounded operations/event regions fill the lower screen. The columns compress at 1920px; below 1450px activity reflows below the core.

The core uses concentric orbits, network paths, nodes, a breathing center, and semantic pathway pulses. Idle is calm; planning/reasoning accelerate; memory, tool, and review illuminate directional paths; testing scans; adjudication converges; completed, warning, and failed use green, amber, and red semantics; listening/speaking reserve a wave treatment. Reduced motion disables continuous movement while preserving labels, color, and geometry.

3090 and 4090 remain separate. The 3090 is PRIMARY / AUTHORITY. The 4090 shows endpoint, eligibility, MO2, and policy reason from snapshot truth. Qwen uses cyan and GLM violet; neither exposes or fabricates thought text. Memory shows metadata counts only. Model review and deterministic acceptance are separate panels.

Transport loss preserves the last snapshot, shows DISCONNECTED and time since update, and marks data stale. Native EventSource reconnection plus refresh-on-reconnect restores live state without rapid polling.

## Security and scope

CSP is self-only with no objects, base, framing, or forms. Static requests cannot select paths. API routes precede static routing, and no upload or mutation route exists. The UI contains no input, button, form, task, memory, routing, or inference control.

Phase 5C does **not** implement real runtime publication wiring, task submission, controls, voice, remote access, or cloud services. Styling is version 1 and remains subject to user review. Phase 5D — Live Runtime Integration is next and has not started.

## Manual inspection

Run `python -m phase5c.run_visual_demo --hold reasoning`, then open `http://127.0.0.1:8766/`. Replace `reasoning` with `idle`, `completed`, or `blocked`; omit `--hold` to loop. Evidence is in `phase5c/evidence/phase5c-acceptance.json`; browser captures are under `phase5c/evidence/screenshots/`.
