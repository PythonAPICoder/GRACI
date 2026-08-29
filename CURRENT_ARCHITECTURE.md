# Current GRACI Architecture

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
Phase 7 remains in progress; Phase 7A and Phase 7B are complete.

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
the optional 4090 remains governed only by the unchanged MO2 policy. Phase 7 remains
in progress; Phase 7A authorizes no deferred Phase 7 or Phase 8 behavior.

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
