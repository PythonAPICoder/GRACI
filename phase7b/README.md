# Phase 7B — Local Operator CLI Integration

Phase 7B makes the ordinary `python -m graci` entry point a thin adapter over the
accepted Phase 7A `ExplicitTurnCoordinator`. Phase 7 remains in progress; Phase 7A
and Phase 7B are complete, while later Phase 7 work remains unauthorized.

## Operator interface

One explicit typed turn:

```powershell
python -m graci "task text"
```

One explicit speech turn:

```powershell
python -m graci --speech
```

Speech mode requires Enter once to initiate capture and again to terminate capture.
It uses the accepted Windows push-to-talk and local faster-whisper CPU path. One
invocation accepts at most one transcript and makes at most one governed submission.
There is no wake word, always-listening behavior, VAD, background microphone,
automatic continuation, retry, second turn, REPL, or conversation loop.

Add `--speak` to either ordinary mode to explicitly request presentation of the
validated final summary. It uses the accepted explicit `AuthoritativeFinalResponse`,
Kokoro CPU `af_bella`, speech-only pronunciation rules, bounded playback, and voice
lifecycle. Without `--speak`, synthesis and playback are never called. Presentation
failure is visible but never changes a governed PASS or its exit code.

## Composition and output

`graci.operator_cli.build_operator_coordinator` composes the existing `Controller`,
Phase 6B push-to-talk/STT, Phase 6D speech presentation, Phase 6E lifecycle, and Phase
7A coordinator. `__main__.py` contains no duplicate submission or presentation
orchestration. The semantic typed/transcribed text is passed unchanged.

The JSON output is an explicit allowlisted projection. It reports source and input
outcome, whether submission occurred, governed outcome and bounded safe result,
final-response availability, requested presentation status, terminal disposition,
and bounded errors. It excludes prompts, reasoning, memory, environment data,
credentials, raw tool output, and generic object reflection. Governed PASS exits
zero; governed FAIL/error and every no-submission terminal result exit nonzero.

The accepted `--workspace`/`--target` Phase 1C mode remains a documented specialized
legacy path because its controlled-action record and security semantics are distinct.
It cannot be combined with voice options, and its permissions are unchanged.

The primary 3090 remains independently sufficient. Voice uses local CPU components
and does not depend on the 4090. Optional 4090 inference remains subject to the exact
unchanged MO2, endpoint, model, freshness, and bounded-fallback policy.

## Verification

- Focused Phase 7B: 13 tests passed; Phase 7B plus Phase 7A regression: 23 passed.
- Full warning-strict suite: 348 tests passed.
- Automated voice coverage uses fakes and requires no microphone, speaker, model,
  network, or 4090.
- Closure evidence: `phase7b/evidence/phase7b-closure.json`.
