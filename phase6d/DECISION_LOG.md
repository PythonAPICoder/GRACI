# Phase 6D Decision Log

- Required explicit `AuthoritativeFinalResponse` construction instead of extracting
  or guessing a response from runtime structures.
- Reused the Phase 6A speech-only lexicon at the last boundary before synthesis.
- Kept Kokoro and playback in one-shot subprocesses for Python-version isolation,
  bounded lifetime, cancellation, failure containment, and deterministic cleanup.
- Fixed production identity to local Kokoro-82M ONNX CPU with `af_bella`; no second
  Piper implementation was needed for this narrow accepted slice.
- Used a zero-length queue: one synthesis and one playback may be outstanding.
- Kept speech results separate from governed task results by architecture.
