# Current GRACI Architecture

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
