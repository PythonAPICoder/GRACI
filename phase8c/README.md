# Phase 8C — Trusted Reactive Presence & Accessible Command Center

Phase 8C improves the localhost Browser UI using only trusted resident snapshot,
SSE, and explicit browser-PTT facts. It adds presentation state, not runtime state or
authority.

## Trusted-state mapping

The frozen frontend maps every existing `SystemState` deterministically. `idle` is
ready/resting; `listening` is receptive; planning, memory retrieval, and reasoning
are processing; tool execution is working; tests, review, and adjudication are
verification; `speaking` is owned playback; terminal completion, warning, and failure
remain distinct. The authoritative `system_state` label stays visible. Unknown values
use warning presentation and fail closed. Disconnect independently marks the last
snapshot stale. No timer, animation, or browser inference creates an activity fact.

Qwen is labeled as the primary local implementer and GLM as the local reviewer. A
configured model is not shown active: active treatment requires trusted `AgentView`
state. The RTX 3090 remains primary and authoritative. The optional RTX 4090 display
distinguishes in-use, healthy/available, MO2-blocked, unhealthy, other policy
ineligibility, and unknown/fail-closed using server-projected compute facts only.
Browser JavaScript does not inspect processes.

Physical QA confirmed that the resident does not currently project an authoritative
3090 health observation. The 3090 therefore says `HEALTH NOT OBSERVED` when endpoint
health is unknown; it does not infer health from a successful earlier Qwen turn. This
presentation-only distinction does not change the optional 4090's fail-closed policy.

## Reactive-presence audit

Comparison with the Phase 8C starting commit classifies the implementation as **B:
mostly reused pre-existing animation machinery while adding trusted state mapping and
presentation**. The existing core already provided idle orbit/breathing, listening
ripple, faster planning/reasoning motion, Qwen reasoning activity, violet GLM review,
speaking pulse, one-shot completion pulse, warning/failure treatments, and CSS state
transitions. Phase 8C retained those intentionally subtle animations and added
deterministic semantic explanations, stricter trusted agent-active display, and
accessibility and responsive refinements. Reduced-motion continues to remove all
animation and transition. No additional animation redesign was warranted.

## Latest response, latency perception, and accessibility

Phase 8B resident `latest_turn` remains the sole source of completed response text.
While a newer trusted task is active, that response is explicitly labeled previous;
a failed turn still cannot fabricate response text. Refresh, polling, SSE reconnect,
multi-tab convergence, replacement, and restart retention remain unchanged.

Truthful semantic copy makes accepted listening, governed processing, review,
speaking, completion, degradation, and failure visible promptly. There are no fake
percentages, token streams, timing promises, speculative calls, or execution changes.
State and latest-response regions are atomic polite live regions, state is never
color-only, focus indication and pointer/Spacebar PTT remain intact, reduced motion
removes animation and transition, and an added narrow breakpoint preserves reading
order and response space.

## Authority and verification

The only buttons remain accepted PTT and Restart GRACI. No endpoint, CORS behavior,
cloud access, model/compute override, command, policy, memory, file, deployment, wake
word, VAD, or always-listening capability was added. Observer/presentation state
cannot grant execution authority.

Deterministic tests cover state mapping, Qwen/GLM active semantics, all bounded 4090
presentations, current/previous latest response behavior, accessibility, reduced
motion, responsive layout, pointer/Spacebar PTT, and the unchanged authority surface.
Automated verification cannot establish physical Browser acceptance.

## Required physical QA

The Product Owner should verify page load/reload; idle; mouse and Spacebar holds;
listening, processing, and speaking transitions; response readability and second-turn
replacement; multi-tab/reload and Restart continuity; reduced motion where practical;
3090/4090 labels; and MO2 blocking only when it can be tested without disruption.

## Phase 8D handoff — System Health & Trusted Runtime Context

Phase 8C does **not** implement startup health checks, periodic health collection,
monitoring loops, or new system/network authority. Phase 8D will own authoritative,
timestamped observations for resident readiness; trusted local date/time/timezone;
3090 node, llama.cpp, and Qwen health; GLM availability; 4090 reachability; MO2 state;
4090 eligibility; 4090 endpoint/model health when policy permits; STT and TTS
readiness; freshness and staleness; degraded, unavailable, recovering, and recovered
transitions; bounded state-change alerts; and bounded trusted conversational system
context.

Physical QA identified two inputs for that phase rather than Phase 8C failures:

- GRACI cannot yet reliably answer current 4090-status questions from authoritative
  resident system state.
- GRACI cannot yet answer current date/time questions from trusted runtime context.
