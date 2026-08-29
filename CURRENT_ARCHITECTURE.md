# Current GRACI Architecture

## QA-001 identity and response separation

`user task -> bounded GRACI system role -> local Qwen -> strict governed result v2 {status, internal summary, user_response} -> validated PASS user_response -> AuthoritativeFinalResponse -> typed JSON and optional local speech`

Qwen is the local reasoning implementation acting for the user-facing GRACI identity;
underlying models may still be disclosed when architecture is explicitly requested.
The validator keeps governed PASS/FAIL independent from presentation and fails closed
on malformed or inconsistent v2 fields. Only a nonblank `user_response` from a
validated v2 PASS can cross the final-response boundary; internal summaries and errors
remain governed diagnostics. Typed and speech input still converge on the same single
submission and response-construction path.

## Phase 8A observer-only presence

`trusted observer system_state -> frozen presentation mapping -> HTML/CSS/SVG presence`

The mapping is not persisted or published. Unknown state uses warning presentation
without replacing its displayed label; freshness independently marks stale data.
The Phase 5 read-only API and static allowlist are unchanged.

## Phase 7 accepted local interaction composition

`explicit operator action -> typed OR explicit push-to-talk -> ExplicitTurnCoordinator -> exactly one governed run(task) -> governed result -> explicit AuthoritativeFinalResponse -> optional local Kokoro CPU speech -> bounded operator result`

Accepted input text is unchanged by source metadata. Accepted turns submit exactly
once; rejected or failed input submits zero times. Serialization, optional
presentation, and lifecycle publication remain non-authoritative. `LISTENING` wraps
only bounded capture/recognition, `SPEAKING` only actual playback, and voice returns
to `IDLE`. There is no retry or automatic second turn.

The ordinary local CLI is the operator surface. Phase 1C workspace/target remains an
intentionally distinct specialized legacy mode; internal/test APIs are not alternate
ordinary surfaces; the browser visualizer remains observer-only. The 3090 remains
independently sufficient and the optional 4090 policy is unchanged. Future interaction
enhancements require a separately authorized later phase.

## Phase 7B local operator adapter

The ordinary CLI is now:

`explicit typed task OR explicit bounded --speech -> Phase 7A ExplicitTurnCoordinator -> existing governed run(task) -> bounded allowlisted JSON -> optional explicit --speak presentation`

`graci.operator_cli` owns only production composition and safe serialization.
`graci.__main__` selects one mode and calls the coordinator once; it contains no
duplicate orchestration or retry. Speech requires distinct operator actions to begin
and end capture and cannot produce a second turn. Presentation is opt-in and its
failure cannot change governed truth. Phase 1C `--workspace`/`--target` remains a
specialized legacy security boundary and cannot be combined with voice options.

No new runtime, execution authority, routing, memory, persistence, network control,
background listener, wake word, VAD, REPL, or autonomous loop exists. Voice remains
local CPU-only. The 3090 is independently sufficient and optional 4090 eligibility,
exact MO2 gating, health/model freshness, and fallback semantics are unchanged.
Phase 7A and Phase 7B are complete and accepted by Phase 7C closure.

## Phase 7A explicit single-turn composition

`graci.turn_coordinator.ExplicitTurnCoordinator` is a small orchestration layer over
accepted interfaces:

`explicit typed input OR explicit Phase 6 push-to-talk transcript -> one shared existing governed run(task) call -> independent governed result -> explicit AuthoritativeFinalResponse construction -> optional accepted Phase 6D presentation -> frozen TurnResult`

`typed` and `speech` are the only structural source values and never modify semantic
task text. Pre-submission rejection yields zero submissions; accepted input reaches
the single submission statement exactly once. The coordinator has no retry loop,
tool, policy, approval, memory, routing, repository, scheduling, persistence, or
lifecycle authority.

Final-response construction remains explicit and typed. Presentation is caller
requested, uses the existing local Kokoro/playback path, and cannot change the prior
governed result. Existing Phase 6 components alone publish bounded `LISTENING` and
`SPEAKING` observation and restore `IDLE`; observer failure remains isolated. There
is no autonomous conversation loop, wake word, always listening, VAD, automatic
follow-up, or background listener. The 3090 remains independently sufficient and
the optional 4090 remains governed only by the unchanged MO2 policy. Phase 7C later
closed the bounded composition; Phase 8 behavior remains unauthorized.

The authoritative detailed history remains `PROJECT_STATE.md`; phase reconstruction
documents live under each `phase*/` directory. Phase 6C connects the independent
local speech-input stack to the existing governed runtime:

`explicit push-to-talk -> Windows PCM capture -> transient WAV -> local faster-whisper -> typed transcription result -> SpeechRuntimeAdapter -> existing governed runtime run(task)`

The adapter accepts only successful, nonblank typed results and passes their exact
text through the same `run(task)` boundary as typed input. It does not add grants,
approval, execution, memory, or validation behavior. Capture, lifecycle orchestration,
STT, and higher-level GRACI behavior remain separate. The runtime has no input-source
metadata facility, so no semantic text is altered to encode speech provenance.
The primary 3090 machine is independently sufficient; STT uses CPU and no cloud or
4090 path. Phase 6D is a separate optional output presentation path:

`explicit AuthoritativeFinalResponse -> speech-only pronunciation copy -> isolated local Kokoro CPU synthesis -> bounded validated WAV -> isolated bounded Windows playback`

It has no runtime extraction or execution capability. Synthesis, playback, timeout,
cancellation, device, worker, and cleanup failures remain presentation results and
cannot replace the authoritative response or governed result. See `phase6c/README.md`
and `phase6d/README.md`.

Phase 6E adds an observer-only publication boundary shared by the two voice paths.
It reuses canonical `SystemState.IDLE`, `LISTENING`, and `SPEAKING`. A guarded
generation lease publishes `LISTENING` from immediately before bounded capture start
through transcription, and `SPEAKING` only around actual playback after synthesis.
Every bounded exit restores `IDLE`. Observer failures are logged/recorded and cannot
alter capture, transcription, playback, presentation, or governed runtime results.
See `phase6e/README.md`.

Phase 6 closes at this bounded composition:

`explicit push-to-talk -> local STT -> existing governed run(task) -> independent governed result -> explicit AuthoritativeFinalResponse -> optional local TTS/playback`

Integrated acceptance composes the existing interfaces with deterministic fakes; no
production coordinator was added. The transcript has typed-input-equivalent authority,
the governed result exists independently of presentation, synthesis remains `IDLE`,
and only bounded capture/recognition and actual playback publish `LISTENING` and
`SPEAKING`. Phase 6 contains no autonomous voice loop. See `phase6/README.md`.
# Phase 8A observer-only presence architecture

`trusted runtime/observer system_state -> frozen frontend mapping -> abstract SVG/CSS presence`

The mapping is a presentation boundary, not a second state machine. It produces one
of resting, receptive, thinking, acting, validating, responding, success, warning,
or failure and never publishes or persists that value. The actual authoritative
state label remains visible. Unknown state falls back to warning presentation, and
connection freshness independently marks stale/disconnected data.

The no-build HTML/CSS/SVG implementation adds no assets, dependencies, endpoint, or
backend field. The Phase 5 three-resource static allowlist and read-only observer API
remain unchanged. Phase 6 voice lifecycle is observed without microphone, speech,
or turn authority. The primary 3090 remains independently sufficient; optional 4090
eligibility and MO2 blocking remain unchanged. Phase 8 is in progress; only Phase 8A
is complete.
