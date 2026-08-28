# Phase 6B Test Log

The focused suite covers
success, exact transitions, repeated cycles, startup/capture/STT failure, insufficient
audio, cancellation, cleanup/retention, malformed worker output, timeout, configuration,
and invalid lifecycle operations. The full warning-strict suite is the regression gate.

- `python -W error -m unittest tests.test_phase6b_speech_input -v`: 16 passed.
- Phase 6A + 6B focused regression: 24 passed.
- `python -W error -m unittest discover -s tests -v`: 278 passed.
- `python -W error -m compileall -q graci phase6b`: passed.
- Concrete worker with cached `small.en`, CPU `int8`, and tracked synthetic
  `phrase-01.wav`: passed locally in 1.69 seconds and returned a real transcript.
- Physical microphone smoke test: not run; optional and not an automated gate.
