# Current GRACI Architecture

The authoritative detailed history remains `PROJECT_STATE.md`; phase reconstruction
documents live under each `phase*/` directory. Phase 6B adds an independent local
speech-input stack:

`explicit push-to-talk -> Windows PCM capture -> transient WAV -> local faster-whisper -> typed transcription result`

Capture, lifecycle orchestration, STT, and higher-level GRACI behavior are separate.
The transcript is not yet connected to the governed runtime and grants no authority.
The primary 3090 machine is independently sufficient; STT uses CPU and no cloud or
4090 path. See `phase6a/ARCHITECTURE.md` for the voice authority boundary and
`phase6b/README.md` for implementation detail.
