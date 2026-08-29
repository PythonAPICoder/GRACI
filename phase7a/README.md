# Phase 7A — Explicit Turn Coordinator

Phase 7 has begun. Phase 7A adds only a production composition layer for one
explicitly initiated user turn. It does not complete Phase 7.

## Architecture

`graci.turn_coordinator.ExplicitTurnCoordinator` accepts either explicitly supplied
typed text or an explicitly begun and ended accepted Phase 6 push-to-talk operation.
Both sources reach one shared coordinator submission statement calling the injected
existing governed `run(task)` boundary. `InputSource.TYPED` and `InputSource.SPEECH`
are structural metadata only; the exact accepted text is not prefixed, tagged, or
rewritten. One accepted input produces exactly one submission. Blank typed input,
failed acquisition, failed transcription, and blank transcription produce zero.

The frozen `TurnResult` composes accepted typed values and reports input source and
outcome, the speech transcription when applicable, submission truth, the governed
result, an explicitly constructed `AuthoritativeFinalResponse`, optional accepted
Phase 6D presentation result, terminal disposition, and bounded error details. It
contains no prompts, raw tool output, memory contents, credentials, or hidden
reasoning. An exception from `run(task)` is recorded as a submitted governed error;
no retry or second submission occurs.

Final-response selection is an explicit injected `FinalResponseConstructor` boundary.
The coordinator does not scrape runtime logs or arbitrary model output. Speech is
performed only when the caller sets `present_speech=True`, an authoritative response
was explicitly constructed, and the accepted `SpeechPresentationService` is present.
The governed result exists first and remains unchanged by synthesis or playback
failure. Existing Kokoro CPU synthesis, `af_bella`, Phase 6A pronunciation, bounded
playback, transient audio, and `SPEAKING` lifecycle behavior are reused unchanged.

The coordinator adds no lifecycle authority. Existing Phase 6 components publish
`LISTENING` only during bounded capture/recognition and `SPEAKING` only around actual
playback, restore `IDLE`, and isolate observer failures. No visual state is fabricated.

## Verification

Deterministic fakes require no microphone, speaker, model, network, cloud, GPU, or
4090. Run:

```powershell
python -W error -m unittest tests.test_phase7a_turn_coordinator -v
python -W error -m unittest discover -s tests -v
python -W error -m py_compile phase6a/pronunciation.py
python -W error -m compileall -q graci phase6b phase6c phase6d phase6e phase6 phase7a tests
```

Compilation remains scoped to GRACI-owned source and tests. The ignored third-party
Tcl/Tix cache diagnostic documented by Phase 6 remains excluded.

## Boundaries and deferred work

There is no wake word, always-listening mode, VAD, autonomous or continuous voice
loop, automatic reopening/follow-up, background agent/listener, scheduler, session
memory, new persistence, HTTP control endpoint, UI, cloud service, provider, model,
inference route, or new tool/repository authority. The 3090 remains independently
sufficient. The 4090 remains optional capacity solely under the existing MO2 policy;
voice does not depend on it. Deferred Phase 7 features require separate authorization.

Durable closure evidence is `phase7a/evidence/phase7a-closure.json`.
