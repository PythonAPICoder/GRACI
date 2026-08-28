# Phase 6B — Push-to-Talk Audio Capture & Local STT

Phase 6B adds input-side voice primitives only. It does not submit transcripts to a
model, invoke tools, write memory, speak a response, publish visualizer state, listen
in the background, or use the optional 4090.

## Architecture and lifecycle

`graci.audio_capture` owns configurable microphone capture. The production adapter
uses the Windows `waveIn` API through the standard library: mono, signed 16-bit PCM,
16 kHz, default input device, 100 ms buffers, 120-second hard maximum, and a 150 ms
minimum utterance. Those values are typed configuration rather than hidden constants.
Audio remains in memory until STT needs a temporary WAV.

`graci.push_to_talk.PushToTalkController` is the small integration surface:
`begin()`, `end_and_transcribe()`, `cancel()`, and observable `state`. Its serialized
flow is `idle -> recording -> transcribing -> completed/failed -> idle`. Invalid or
overlapping operations fail deterministically. Capture startup errors raise after a
failed-to-idle transition; post-start capture and STT failures return typed failures.

`graci.speech` defines immutable captured-audio and transcription contracts plus the
replaceable `SpeechToText` protocol. Results distinguish success/failure, text,
backend identity, utterance duration, error code, and bounded diagnostic message.
Failure never invents text.

The production STT adapter invokes `phase6b/stt_worker.py` in a configured Python
environment. The worker uses faster-whisper `small.en`, CPU `int8`, the Phase 6A
local cache, and `local_files_only=True`; runtime model downloading and cloud STT are
impossible through this path. Subprocess isolation avoids making faster-whisper a
mandatory import of the main GRACI runtime and preserves the qualified environment.

## Privacy and cleanup

Capture begins only when `begin()` is explicitly called. There is no background
thread before that action and no wake word or always-listening mode. Temporary WAVs
are removed in a `finally` block after success, worker failure, malformed response,
timeout, or process-start failure. `retain_audio=False` is the default. The optional
manual `--retain-audio` switch writes only to ignored `phase6b/debug-audio/`.

## Verification

Automated tests use fake capture sessions and STT adapters, requiring no microphone,
speech, network, model, GPU, or 4090. Adapter tests mock the worker boundary and check
WAV existence during invocation and deletion afterward. Run:

```powershell
python -W error -m unittest tests.test_phase6b_speech_input -v
python -W error -m unittest discover -s tests -v
```

Optional manual smoke test (requires a populated local model cache):

```powershell
python -m phase6b.manual_push_to_talk
```

## Known limitations and deferred work

The worker cold-loads the model for each utterance; a warm bounded worker may be
introduced later without changing the STT interface. Audio-device enumeration and a
polished hotkey/UI are deferred. Phase 6C transcript/runtime integration, TTS,
playback, LISTENING/SPEAKING publication, wake word, turn-taking, VAD-driven listening,
barge-in, duplex speech, and 4090 scheduling are explicitly absent.
