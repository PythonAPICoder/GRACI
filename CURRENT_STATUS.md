# Current GRACI Status

## Phase 7A explicit turn coordinator — COMPLETE

Phase 7 has begun and remains in progress. Phase 7A provides only explicit
single-turn coordination. Typed text and accepted Phase 6 push-to-talk transcripts
share the existing governed `run(task)` authority boundary. One accepted explicit
turn submits exactly once; rejected or blank input submits zero times. Input-source
metadata is structural and does not alter task text.

The governed result is independent of an explicitly constructed
`AuthoritativeFinalResponse` and caller-requested local speech presentation. Existing
Phase 6 lifecycle observation remains non-authoritative and restores `IDLE`; failures
in observation, TTS, or playback do not replace governed truth. No wake word,
always-listening mode, autonomous conversation loop, automatic follow-up, new
persistence, control API, or routing policy was added. The 3090 remains sufficient;
the 4090 remains optional under unchanged MO2 policy. Later Phase 7 capabilities are
deferred. Evidence is `phase7a/evidence/phase7a-closure.json`.

- Phases 1–5: complete.
- Phase 6A voice qualification: complete.
- Phase 6B push-to-talk/local STT: complete; verification is recorded in
  `phase6b/TEST_LOG.md` and `phase6b/evidence/phase6b-closure.json`.
- Phase 6C governed runtime transcript integration: complete; successful nonblank
  transcripts enter the ordinary governed `run(task)` boundary unchanged.
- Phase 6D local TTS and bounded audio playback: complete. Only an explicitly
  constructed authoritative final response can enter the optional presentation path.
- Phase 6E voice lifecycle publication: complete. Canonical `LISTENING` and
  `SPEAKING` facts wrap only bounded listening/recognition and actual playback;
  observer failures are isolated and all exits restore `IDLE`.
- **Phase 6 complete — bounded push-to-talk voice architecture accepted.** Integrated
  deterministic acceptance composes the existing 6B–6E interfaces without a new
  production coordinator, execution path, authority, network dependency, scheduling,
  or persistence.
- All later voice-loop behavior remains deferred. No Phase 6F is named or authorized;
  any future voice enhancement requires separate roadmap authorization.

GRACI remains local-first and fully functional on the primary RTX 3090 machine alone.
No cloud speech service or optional 4090 capacity is required.
