# Phase 6B Decision Log

- Retained the Phase 6A decision: faster-whisper `small.en` on primary-machine CPU
  `int8`. It was the simplest qualified local baseline, matched the larger model's
  measured corpus WER, and avoided competing for 3090 VRAM or depending on the 4090.
- Used a subprocess adapter with `local_files_only=True` so the existing qualified
  environment/cache remains isolated and runtime cannot download a model.
- Used Windows `waveIn` behind an audio interface because the host had no microphone
  package installed. This adds no new Python compatibility or persistent-service
  dependency.
- Kept audio transient by default and made debug retention explicit and ignored.
- Kept transcript-to-runtime integration out of scope; the result has no authority.
