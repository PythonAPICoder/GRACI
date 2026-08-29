# Phase 7C — Integrated Local Interaction Acceptance and Phase 7 Closure

Phase 7C accepts the existing Phase 7A/7B production composition without adding a
new interaction paradigm or runtime path:

`explicit typed input OR explicit push-to-talk -> ExplicitTurnCoordinator -> one governed run(task) -> governed result -> explicit AuthoritativeFinalResponse -> optional local speech -> bounded CLI result`

The deterministic integration suite enters through the real CLI, uses the production
coordinator factory, and retains the real Phase 6 push-to-talk, lifecycle,
speech-presentation, and Phase 7 coordinator objects. Only the governed runtime and
hardware/process boundaries are replaced with fakes.

Acceptance proves exact text preservation and exactly one submission for accepted
typed and speech input; blank, failed, or rejected pre-submission input produces zero.
One speech invocation captures and transcribes once and cannot automatically reopen.
Typed mode is microphone- and presentation-inert by default. `--speak` alone permits
the accepted Kokoro CPU `af_bella` path from an explicit authoritative response, with
the Phase 6A speech-only pronunciation copy. Synthesis, playback, and observer failures
cannot change governed truth. Lifecycle returns to `IDLE` after bounded activity.

The ordinary CLI is the accepted operator surface. Phase 1C workspace/target remains
a distinct specialized legacy mode. Internal/test APIs are not alternate ordinary
surfaces, and the browser visualizer remains observer-only. No cloud dependency,
control server, persistence, routing change, autonomous loop, listener, retry, or
alternate speech provider was added.

Verification:

```powershell
python -W error -m unittest tests.test_phase7c_integrated_acceptance -v
python -W error -m unittest tests.test_phase7a_turn_coordinator tests.test_phase7b_operator_cli tests.test_phase7c_integrated_acceptance -v
python -W error -m unittest discover -s tests -v
python -W error -m py_compile phase6a/pronunciation.py
python -W error -m compileall -q graci phase6b phase6c phase6d phase6e phase6 phase7a phase7b phase7c phase7 tests
```

Evidence is `phase7c/evidence/phase7c-closure.json`; consolidated evidence is
`phase7/evidence/phase7-closure.json`.
