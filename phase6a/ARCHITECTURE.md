# Phase 6 voice architecture proposal

Phase 6 uses push-to-talk. Voice is outside GRACI's authority boundary.

## Components and ownership

- `VoiceCapture` (6B): explicit press/release, one local mono PCM buffer, hard duration/size limits, transient by default.
- `SpeechToText` (6B): local faster-whisper worker, CPU `int8`, model kept warm when enabled, bounded transcript/result metadata.
- `VoiceInputAdapter` (6C): validates and labels the transcript as untrusted user input, then calls the existing governed input boundary. It owns no tool, routing, memory, approval, or policy capability.
- `TextToSpeech` (6D): accepts only the authoritative final user-facing response. It derives a bounded speech-presentation copy through an explicit technical pronunciation lexicon, then sends only that copy to Kokoro. The authoritative response is never mutated. The selected implementation target is Kokoro ONNX on CPU with `af_bella`; Piper is the reliability fallback.
- `AudioPlayback` (6D): local bounded queue, stop/cancel, no network, no authority.
- `VoiceLifecycleObserver` (6E): observes trusted capture/playback boundaries and publishes LISTENING/SPEAKING later. It cannot affect execution and is not implemented in 6A.

Data flow: explicit push-to-talk -> bounded transient local audio -> local STT -> untrusted transcript -> existing governed GRACI input boundary -> normal runtime -> authoritative final response -> local TTS -> local playback.

Audio is never sent to a cloud service. Raw microphone audio is not persisted unless the user explicitly requests it. Transcripts have exactly typed-input authority. TTS may never receive chain-of-thought, hidden reasoning, raw reviewer rationale, internal evidence, raw stdout/stderr, environment dumps, secrets, credentials, tokens, or memory content that was not intentionally included in the final response.

The voice system must not authorize tools, modify routing, write memory by itself, approve actions, change reviewer/adjudication results, bypass MO2 restrictions, or invoke cloud services. Failures are contained: STT failure returns no input; TTS/playback failure does not change the completed task result.

## Qualification decision

Use faster-whisper `small.en`, CPU `int8`, as the Phase 6B baseline on this machine. The measured aggregate RTF was 0.395 versus 1.656 for `large-v3-turbo`; both had 0.1296 WER on the small synthetic technical corpus. Keep a user-configurable technical vocabulary/hotword strategy for GRACI/Qwen/llama.cpp, but never silently rewrite transcripts.

Do not use GPU voice inference by default. At inventory time the 3090 had 23,228 of 24,576 MiB in use by the existing workload. GPU qualification was therefore not practical without displacing GRACI inference; 4090 use is not required or assumed. A later opportunistic GPU mode may run only under existing capacity policy and must fall back to CPU.

Kokoro-82M ONNX CPU with `af_bella` is the user-selected preferred Phase 6 production voice. The deterministic speech-only lexicon maps only the whole tokens `GRACI` to `GRAY-see`, `3090` to `thirty ninety`, and `4090` to `forty ninety`; displayed, stored, logged, remembered, reviewed, and adjudicated text remains unchanged. There is no generic number rewriting. Piper CPU is the fallback. Chatterbox remains a quality reference but was not executed: its 500M/PyTorch and reference-voice workflow add resource, consent, and deployment complexity.
