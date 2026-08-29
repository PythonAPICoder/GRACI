# Phase 8A — Observer-Only Presence Foundation

Phase 8A establishes the first bounded GRACI presence layer. Existing trusted
`system_state` remains authoritative and maps in the no-build frontend to one of
nine presentation-only categories: resting, receptive, thinking, acting,
validating, responding, success, warning, or failure. The category is neither
persisted nor published to runtime.

The abstract SVG core now carries a readable authoritative state, a secondary
presentation category, and deterministic static and animated cues. Unknown state
values use warning presentation while retaining their supplied label. Stale or
disconnected transport dims the presence and labels it stale. Reduced-motion mode
removes animation while text, geometry, border, and color distinctions remain.

The Phase 5 observer boundary is unchanged: three same-origin static resources and
GET/HEAD observer APIs only. There are no task, voice, microphone, speech, routing,
memory, persistence, or runtime controls. LISTENING, SPEAKING, and IDLE are observed
lifecycle facts only. The 3090 remains independently sufficient; the 4090 remains
optional and blocked whenever the unchanged MO2 policy requires it.

Phase 8 remains in progress. Phase 8B and later refinement, conversation UI,
continuous listening, autonomous follow-up, and all new authority are deferred and
unauthorized.
