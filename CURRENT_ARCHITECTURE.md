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
