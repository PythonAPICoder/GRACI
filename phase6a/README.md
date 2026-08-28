# Phase 6A — Voice Qualification & Architecture

Phase 6A is complete as qualification evidence only. It adds no microphone capture, live transcript submission, production TTS playback, LISTENING/SPEAKING publication, wake word, or always-listening service.

## Measured local results

All STT runs used the same 24.147-second synthetic Piper corpus (14 files) and local execution.

| Engine/model | Mode | Cold load/start | Transcription | Aggregate RTF | WER |
|---|---|---:|---:|---:|---:|
| faster-whisper large-v3-turbo | CPU int8 | 31.418 s | 39.979 s | 1.656 | 0.1296 |
| faster-whisper small.en | CPU int8 | 10.420 s | 9.539 s | 0.395 | 0.1296 |
| whisper.cpp b4938 small.en | CPU f16 | included per-process | 34.301 s | 1.421 | 0.1111 |

The corpus is synthetic and intentionally stresses short technical names; it is decision evidence, not a general accuracy claim. Full sentences retained good punctuation. Frequent errors were GRACI -> Grassi/Grasi, Qwen -> You win, and llama.cpp -> lana.cpp. Failure behavior was bounded nonzero exit/exception and no submission to GRACI.

The 3090 inventory was 23,228/24,576 MiB used. GPU STT/TTS was not practical without evicting or competing with GRACI inference. CPU-first preserves Qwen and requires neither the 4090 nor stopping llama.cpp.

## Audition pack

Six identical lines were generated for each voice:

- Kokoro: `af_heart`, `af_bella`, `af_nicole`
- Piper: `en_US-amy-medium`, `en_US-hfc_female-medium`, `en_US-lessac-medium`

Listen to Piper under `phase6a/artifacts/audition/<voice>/line-01.wav` through `line-06.wav`, and Kokoro under `phase6a/artifacts/audition/kokoro/<voice>/line-01.wav` through `line-06.wav`. The user selected Kokoro `af_bella` as the preferred Phase 6 production voice. The original pack remains as decision evidence. Model caches are excluded.

## Final pronunciation decision

`GRACI` must be spoken as `GRAY-see`, `3090` as `thirty ninety`, and `4090` as `forty ninety`. `pronunciation.py` implements these three bounded, explicit whole-token technical entries and derives a speech-presentation string immediately before TTS. It does not mutate the authoritative response, conversation text, memory, evidence source text, logs, task input, reviewer output, adjudication, or stored project data. Unrelated numbers are unchanged; this is not a broad rewriting system.

The four final `af_bella` pronunciation samples and their separate source/presentation evidence are under `artifacts/audition/finalist-af_bella/`. Their authoritative source fields retain `GRACI`; only `speech_presentation_text` contains `GRAY-see`. An offline back-check with the cached faster-whisper `small.en` model transcribed all four spoken names as “Gracie.” faster-whisper `small.en` CPU `int8` remains the recommended Phase 6B STT baseline.

The follow-up GPU-number listening set is under `artifacts/audition/technical-pronunciation-af_bella/`. Its manifest preserves the four authoritative sentences with numeric `3090`/`4090` and separately records the speech strings with `thirty ninety`/`forty ninety`.

Piper generation was roughly 1.3 seconds per line on CPU. Kokoro used the 88 MiB int8 ONNX model and CPU provider; its detailed per-line timing is in `artifacts/audition/kokoro-generation.json`. The original Kokoro Python frontend was blocked by Windows Application Control while importing a spaCy DLL; the ONNX path succeeded.

## Reconstruct

Create isolated environments from `requirements-stt.txt` and `requirements-kokoro.txt`. Kokoro requires Python 3.10–3.12 (qualification: 3.12.11); the host Python 3.14 is unsuitable. Download models only during installation, then run with network disabled. Caches belong in `phase6a/cache/` and are ignored.

Run `generate_piper_assets.py`, `benchmark_faster_whisper.py`, `benchmark_whisper_cpp.py`, and `generate_kokoro_assets.py --model <kokoro-int8.onnx> --voices <voices.bin>`. Exact configuration is in `qualification_config.json`; durable summarized evidence is `evidence/phase6a-qualification.json`.

## Dependencies and licenses

Verified upstream at qualification time: faster-whisper 1.2.1 (MIT; CTranslate2 runtime, PyAV), OpenAI Whisper code/weights (MIT), whisper.cpp b4938 (MIT), Kokoro-82M weights/voice pack (Apache-2.0), Chatterbox code/weights (MIT), and current Piper 1.4.1 engine (GPL-3.0). Piper voice licenses are per-voice metadata and must be checked before redistribution; the aggregate legacy repository label is not sufficient proof for every voice. No unverified voice-license claim is made.

Deployment caveats: faster-whisper GPU needs matching CUDA 12/cuBLAS/cuDNN 9; Windows Hugging Face caching cannot use symlinks without Developer Mode; Piper 1.4.1 omitted a CLI dependency on `pathvalidate`; Chatterbox adds a large PyTorch stack and voice-reference consent requirements; model/package caches are hundreds of MB to multiple GB and are never committed.
