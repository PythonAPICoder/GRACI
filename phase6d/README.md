# Phase 6D — Local TTS and Bounded Audio Playback

Phase 6D adds optional output presentation only. It does not run a task, inspect a
runtime result, select text, grant authority, or affect deterministic acceptance.

## Authoritative input boundary

`AuthoritativeFinalResponse` is an immutable value that a caller must construct from
text already selected as the authoritative final user-facing response. Raw strings
are rejected by `TTSRequest` and `SpeechPresentationService`. Phase 6D has no adapter
that scrapes dictionaries or concatenates runtime fields, so planner/implementer/
reviewer reasoning, adjudication rationale, prompts, evidence, logs, traces, tool
data, exceptions, secrets, credentials, metadata, and diagnostics cannot enter by
inference.

The authoritative string remains unchanged. Immediately before synthesis,
`phase6a.pronunciation.speech_presentation_text` derives a separate bounded speech
copy. Whole-token `GRACI` becomes `GRAY-see`; `3090` and `4090` become `thirty ninety`
and `forty ninety`. Stored, displayed, logged, returned, and governed text is not
rewritten.

## Synthesis and playback

`KokoroSubprocessTTS` starts the qualified Python 3.12 environment for each explicit
request and invokes `phase6d/tts_worker.py`. The worker accepts only `af_heart`, CPU,
local model/voice paths, and bounded file inputs. Synthesis remains fixed at speed
`1.00`. It uses Kokoro-82M ONNX and writes a mono 16-bit PCM WAV. The parent validates
the strict JSON identity and the WAV before
exposing immutable audio bytes. The worker is not resident and has no download,
cloud, GPU, or 4090 path.

`SubprocessWavePlayback` writes the validated bytes to a transient WAV and invokes a
one-shot blocking Windows `winsound` worker. The parent can terminate it through
`stop()`/`cancel()`. Synthesis and playback each permit one outstanding operation;
additional attempts fail with `synthesis_busy` or `playback_busy` rather than queue.

Bounds are 20,000 input characters, 8 MiB WAV, 120 seconds audio, 60 seconds synthesis,
125 seconds playback, and two seconds for terminate-before-kill cleanup. Temporary
speech text, synthesized WAV, and playback WAV are removed after success, failure,
timeout, or cancellation. Cleanup failures are explicit subsystem failures.

`SpeechPresentationService` catches synthesis and playback exceptions and returns a
separate immutable presentation result. It receives no runtime object and cannot
modify, replace, cancel, or roll back a governed result. `stop()` affects only the
synthesizer/player.

## Verification and reconstruction

Run deterministic tests without audio hardware, models, network, or the 4090:

```powershell
python -W error -m unittest tests.test_phase6d_tts_playback -v
python -W error -m unittest discover -s tests -v
```

With the ignored qualified Phase 6A Python 3.12 environment and caches present, run:

```powershell
python -m phase6d.run_live_qualification
```

The accepted live fixture produced 3.563 seconds of 24 kHz mono 16-bit audio using
local Kokoro `af_bella`; the WAV was validated and hashed, then discarded. Physical
speaker playback was not performed. Evidence is under `phase6d/evidence/`.

Wake word, automatic/continuous listening, VAD, duplex speech, barge-in, automatic
speech loops, visualizer LISTENING/SPEAKING publication, cloud speech, 4090 scheduling,
distributed speech, and Piper implementation remain outside Phase 6D.
