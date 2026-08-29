# Current GRACI Status

## Windows startup and resident host — COMPLETE IN REPOSITORY

The authoritative 3090 now has one supported idle resident composition. It owns one
accepted GRACI runtime instance and the loopback-only observer visualizer continuously,
publishing initial `IDLE` without starting a governed run. Startup performs no task
submission, microphone activation, wake word, VAD, continuous listening, or automatic
follow-up. Resident does not mean autonomous, and the microphone remains inactive
until an explicit accepted push-to-talk operator action.

`ops/start-graci-resident.ps1`, `status-graci-resident.ps1`, and
`stop-graci-resident.ps1` provide bounded lifecycle operations. Explicit install and
remove scripts manage only the named current-user Task Scheduler entry. Repository
tests do not install it; real Task Scheduler validation remains a manual 3090
acceptance step. Existing model routing, 4090 policy, memory, and governed execution
boundaries are unchanged.

The accepted login composition also has a distinct `GRACI 3090 llama.cpp Router`
current-user task. Both it and `GRACI Resident Host` use hidden noninteractive task
actions and hidden, logged child processes. Router startup preserves loopback-only
native model-directory/autoload mode and does not preload a model; existing leases
and health checks remain authoritative. The two tasks are failure-isolated.

## QA-006 canonical identity definition — REPAIRED

The product-owner canonical expansion is **G.R.A.C.I. = General Reasoning And
Conversational Intelligence**. This supersedes the former expansion while preserving
historical records as written. The bounded QA-001 identity contract answers acronym
questions with this exact wording and forbids invented or substituted expansions.

## QA-003 authoritative 3090 Qwen/GLM availability — REPAIRED

The production localhost endpoint had been launched as a single Qwen model server,
so `/v1/models` could not truthfully resolve GLM review. GRACI now uses the installed
llama.cpp router's bounded on-demand model lifecycle: both approved local GGUFs are
discoverable, only one may be loaded, and a serialized verified lease selects Qwen
or GLM before inference. The manual operator scripts are
`ops/start-3090-llama-router.ps1` and `ops/stop-3090-llama-router.ps1`.

The currently running legacy single-Qwen process has not been stopped by this repair,
because its process ownership could not be established safely. An operator must make
the one-time controlled transition described in the root README. QA-006, web PTT,
auto-start/resident-host behavior, Phase 8B, and optional 4090 policy are untouched.

## QA-001 GRACI identity and response contract — REPAIRED

Ordinary local model execution now uses a bounded GRACI role instruction and strict
schema-v2 result envelope. Governed `status` and internal `summary` remain available
for execution truth and diagnostics; a distinct `user_response` is the only successful
model field eligible for typed or optional speech presentation. Legacy schema v1
remains accepted for historical compatibility but cannot be promoted into an ordinary
final response. No routing, memory, authority, follow-up, session, or voice-loop policy
changed.

## Phase 8 presence and visual identity — IN PROGRESS

**Phase 8A — COMPLETE.** Existing trusted `system_state` drives nine bounded,
frontend-only presence categories while the exact state and stale/disconnected
truth remain visible. Reduced motion preserves static and textual semantics. No
write/control API or runtime authority was added; voice is observed only, the 3090
remains independently sufficient, and optional 4090/MO2 policy is unchanged.

## Phase 7 bounded explicit local interaction — COMPLETE

**Phase 7 — COMPLETE AT BOUNDED EXPLICIT LOCAL INTERACTION.** Phase 7C exercises
the ordinary production CLI and factory with the Phase 7A coordinator, governed
runtime boundary, Phase 6 push-to-talk and optional Kokoro presentation, and
observer-only lifecycle composition. Accepted typed or speech input submits exactly
once; rejected or failed pre-submission input submits zero times. Governed truth is
unchanged by serialization, observation, synthesis, or playback failure.

The local CLI is the normal operator surface. Phase 1C workspace/target remains a
specialized legacy mode. The 3090 remains independently sufficient and the 4090
remains optional under unchanged MO2 policy. Future interaction enhancements require
a separately authorized later phase; wake word, VAD, sessions/history, automatic
follow-up, autonomous conversation, browser control, new persistence, and Phase 8
presence work are not accepted.

## Phase 7B local operator CLI integration — COMPLETE

Phase 7A and Phase 7B are complete and accepted by Phase 7C closure.
Ordinary `python -m graci "task"` interaction now enters the accepted Phase 7A
coordinator and its single existing governed `run(task)` submission statement.
`--speech` is one explicit push-to-talk turn: hold Spacebar to capture and release
Spacebar to stop and transcribe; `--speak` is explicit opt-in presentation through
accepted local Kokoro `af_bella`. Typed mode never captures audio and presentation
is absent by default.

The CLI emits a bounded allowlisted JSON projection and deterministic exit status.
One accepted input submits exactly once; rejected input submits zero times; there is
no CLI retry. Presentation failure remains visible without changing governed PASS.
The Phase 1C `--workspace`/`--target` security boundary remains a specialized legacy
path. There is no wake word, always-listening mode, background capture, VAD, REPL,
automatic follow-up, or conversation loop. The 3090 remains independently sufficient
and the 4090 remains optional under unchanged MO2 policy. Evidence is under `phase7b/`.

## Phase 7A explicit turn coordinator — COMPLETE

Phase 7A provides only explicit
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
the 4090 remains optional under unchanged MO2 policy. Phase 7C later accepted this
bounded composition. Evidence is `phase7a/evidence/phase7a-closure.json`.

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
# Phase 8 presence and visual identity — IN PROGRESS

## Phase 8A observer-only presence foundation — COMPLETE

Phase 8A deterministically presents existing trusted `system_state` values through
nine bounded visual categories while retaining the exact authoritative label. The
categories are frontend-only and are not persisted or returned to GRACI. Unknown
values fail safely to warning presentation; stale/disconnected transport remains
explicit. Reduced-motion users retain textual and static semantic distinctions.

No visualizer write/control API, voice control, task submission, routing, memory, or
persistence behavior was added. LISTENING, SPEAKING, and IDLE are observed only. The
3090 remains independently sufficient, and optional 4090/MO2 policy is unchanged.
Phase 8B and later presence work remains unauthorized.
