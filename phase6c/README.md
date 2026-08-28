# Phase 6C — Governed Runtime Transcript Integration

Phase 6C adds `graci.speech_runtime.SpeechRuntimeAdapter`, a deliberately thin boundary
between the Phase 6B typed transcription result and GRACI's normal governed runtime
`run(task)` input. The adapter accepts a `TranscriptionResult`, rejects failed or blank
results, submits the exact successful transcript string once, and returns the
runtime's existing result unchanged. Runtime submission exceptions remain explicit.

Speech and equivalent typed input therefore traverse the same runtime validation,
provider, execution, persistence, permissions, memory, and authority controls. The
transcript cannot approve work or add authority. The existing runtime input/record
contract has no source-provenance field, so this phase does not alter transcript text
or expand persistence solely to mark speech origin.

Capture and local STT remain Phase 6B responsibilities. Phase 6C adds no microphone,
model, network, GPU, or third-party dependency. It also adds no TTS, playback, wake
word, autonomous listening, VAD loop, duplex behavior, barge-in, GUI redesign, or 4090
speech scheduling. GRACI does not yet speak its response.

Verification uses deterministic fakes around the existing runtime boundary:

```powershell
python -W error -m unittest tests.test_phase6c_runtime_transcript -v
python -W error -m unittest tests.test_phase6b_speech_input -v
python -W error -m unittest discover -s tests -v
python -W error -m compileall -q graci phase6b phase6c
git diff --check
```
