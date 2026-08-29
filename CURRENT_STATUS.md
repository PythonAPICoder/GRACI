# Current GRACI Status

Proposed G1 governance pending Product Owner acceptance is in
[`governance/CURRENT_POLICY.md`](governance/CURRENT_POLICY.md) and
[`governance/POLICY_INDEX.md`](governance/POLICY_INDEX.md). It is not yet accepted
policy. This file reports implementation status and evidence; it does not
independently grant authority.

## Phase 8B resident latest-turn continuity — COMPLETE IN REPOSITORY

The resident visualizer now projects one bounded latest completed browser turn in
snapshot schema v2. It is sourced only from an already-completed submitted
`TurnResult`; successful text must already be a validated
`AuthoritativeFinalResponse`. Governed failure exposes bounded status without a
fabricated response, and speech outcome remains separate.

This process-memory value survives refresh, SSE reconnect, additional localhost
tabs, a subsequent active task, and Restart GRACI. Resident exit discards it. No
conversation history, run-file reconstruction, transcript display, typed browser
submission, new route, or execution authority was added. Physical multi-tab/browser
acceptance remains a manual product-owner item.

## Governed model JSON reliability — REPAIRED IN REPOSITORY

The two retained failures (`b1f1ab3d-c0f5-437b-bd6b-66b7af9a1eba` and
`52c61db8-f7ed-45eb-b352-974224443c8f`) both received HTTP 200 from the correct
local Qwen model and then failed strict parsing with `Expecting value`. Historical
run records did not retain assistant content, so their byte-exact payload cannot be
recovered. Router evidence proves neither request was truncated. Exact production
request replays reproduced the raw failure class: llama.cpp returned a complete JSON
object inside a ` ```json ` markdown fence despite `response_format=json_object`;
the provider correctly passed that text unchanged to the strict validator.

The production governed-result request now uses the installed llama.cpp build's
native strict `json_schema` response format with exact v2 PASS/FAIL alternatives.
No fence stripping, brace extraction, repair parsing, or permissive normalization was
added. The existing validator still decides success. One corrective generation retry
is allowed only after model-content validation rejection, under the same governed run
and authoritative task. Attempts retain raw content, HTTP/model identity, validation
diagnostic, and outcome. No tool is available in this response-generation stage, and
the ExplicitTurnCoordinator still submits the runtime exactly once. Exhaustion fails
normally and produces no authoritative response.

Warning-strict focused verification passes 56/56 and the complete suite passes
452/452. Project-source compileall, the repository JavaScript syntax check, and
`git diff --check` pass. Live localhost verification reproduced both original tasks
as fenced JSON under the former `json_object` request, proved native strict schema
output without fences, recovered an injected observed-class first attempt through one
real Qwen retry in one durable run, and completed ordinary governed run
`5f6cb6fe-3434-4e0c-9c02-b6cc0b652c3e` on attempt 1. The restarted resident returned
`ready`/`IDLE` while retaining resident PID 12040 and router PID 10408. No physical
Spacebar acceptance was rerun; that remains the product owner's final follow-up.

## Explicit PTT speech barge-in — IMPLEMENTED

Browser pointer/Spacebar PTT and CLI Spacebar PTT may now interrupt only an active
owned Windows playback operation. The already-constructed `AuthoritativeFinalResponse`
and completed governed result remain unchanged; the interrupted presentation returns
`CANCELLED`. The guarded voice lease moves from `SPEAKING` to `LISTENING`, invalidates
the old speaking lease, and starts capture only after the bounded playback stop call
returns. Release remains the sole transcript/submission boundary. Press alone,
duplicate press, cancellation, blank/failed STT, capture-start failure, and timeout
produce zero new governed runs.

Browser processing and deferred-STT objects are turn-scoped, so completion cleanup
from the interrupted request cannot cancel or submit the new hold. Natural playback
completion racing the press is accepted only when the same speaking generation ended;
late old-lease cleanup cannot restore over a newer listening lease. Playback stop uses
only the existing owned subprocess handle, with its existing terminate/wait/kill bound;
no process-name kill, cloud service, always-listening mode, wake word, VAD authority,
or 4090 dependency was added. Streaming STT, QA-007 normalization, `af_heart` at 1.00,
and `GRAY-see` remain unchanged.

Physical Browser Spacebar acceptance passed on 2026-08-29: keydown during
`SPEAKING` stopped owned playback and entered `LISTENING`; release submitted the
single transcript `Hello, Gracie.` through exactly one governed run. Resident events
show one listening event, one release/idle event, one task start, and one Qwen run,
with no duplicate capture, transcript, submission, repeat, or stale-key cleanup.
That governed run independently failed strict response validation with
`validation_error: model output is not valid JSON: Expecting value`. Model-output
At that acceptance point JSON reliability was a separate follow-up defect. It was
subsequently repaired by the structured-response hardening above.

The explicit localhost-only `Restart GRACI` recovery returned `ready` and `IDLE`,
preserved the failed durable run byte-for-byte and retained its event evidence, and
did not replace the resident or llama.cpp router processes. Verification passes
38/38 focused and 448/448 complete warning-strict tests. A bounded Windows check used the real playback worker and an
existing 7.445-second local `af_heart` WAV: playback was confirmed active, explicit
listening entry stopped it with a measured 0.531 ms call interval, playback returned
`cancelled`, state was `LISTENING`, the playback thread ended, and no owned process
remained.

## Windows startup and resident host — COMPLETE IN REPOSITORY

The authoritative 3090 now has one supported idle resident composition. It owns one
accepted GRACI runtime instance and the loopback-only visualizer continuously,
publishing initial `IDLE` without starting a governed run. Startup performs no task
submission, microphone activation, wake word, VAD, continuous listening, or automatic
follow-up. Resident does not mean autonomous, and the microphone remains inactive
until an explicit accepted push-to-talk operator action.

`ops/start-graci-resident.ps1`, `status-graci-resident.ps1`, and
`stop-graci-resident.ps1` provide bounded lifecycle operations. Explicit install and
remove scripts manage only the named current-user Task Scheduler entry. Repository
tests do not install it; real Task Scheduler validation remains a manual 3090
acceptance step. Existing model routing, 4090 policy, memory, and governed execution
boundaries are unchanged. Its one browser operator capability is explicit hold-to-talk:
pointer hold or Spacebar outside normal text-entry/editor contexts. During the hold,
rolling transient PCM snapshots begin local faster-whisper work; release remains the
sole submission boundary and finalizes the complete recording before exactly one
governed coordinator turn. A successful turn shows and speaks the same validated
authoritative response through existing Phase 6D Kokoro/Windows playback.
Presentation failure cannot change
the successful governed result or cause another run. Cancellation, blank/failed STT,
invalid audio, and contention submit zero runs.

The CLI Spacebar path uses the same deferred design through in-memory capture
snapshots. Incremental transcript text is never exposed, persisted, routed, placed in
memory, or submitted. Latest-only snapshot replacement avoids text concatenation at
chunk boundaries; the released full recording is the correctness boundary. The
installed faster-whisper 1.2.1 worker loads once per explicit PTT turn and has no
token streaming contract, so this phase uses a latest-only three-second rolling
preview rather than
claiming native token streaming. Local CPU `int8`, 3090 sufficiency, QA-007 speech
normalization, `af_heart`/1.00 Kokoro presentation, and `GRAY-see` pronunciation are
unchanged.

Bounded 2026-08-29 machine verification used the installed local faster-whisper
environment/cache and existing `phase6a` corpus audio without activating a microphone.
A six-second simulated hold offered six snapshots, launched one turn-scoped worker/model,
performed six previews plus one final request in 7.034 seconds, and finalized after
release in 1.030 seconds. A ten-offer burst started only one preview before release
and performed only two requests total (one preview and one final), demonstrating
latest-only replacement rather than backlog accumulation. Cancellation returned
immediately and its worker had exited within three seconds. Governed calls remained
zero before release and exactly one followed finalization. The
finalization-to-submission interval was not separately instrumented. Physical Browser
Spacebar acceptance was subsequently completed during barge-in acceptance. Physical
CLI Spacebar microphone acceptance remains unrecorded.

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

**Phase 8A and Phase 8B — COMPLETE.** Existing trusted `system_state` drives nine bounded,
frontend-only presence categories while the exact state and stale/disconnected
truth remain visible. Reduced motion preserves static and textual semantics. No
Phase 8A itself added no control or runtime authority. Later accepted resident work
added only explicit Browser PTT and Restart GRACI. Phase 8B adds read-only latest-turn
continuity without expanding those controls. The 3090 remains independently
sufficient, and optional 4090/MO2 policy is unchanged.

## Phase 7 bounded explicit local interaction — COMPLETE

**Phase 7 — COMPLETE AT BOUNDED EXPLICIT LOCAL INTERACTION.** Phase 7C exercises
the ordinary production CLI and factory with the Phase 7A coordinator, governed
runtime boundary, Phase 6 push-to-talk and optional Kokoro presentation, and
observer-only lifecycle composition. Accepted typed or speech input submits exactly
once; rejected or failed pre-submission input submits zero times. Governed truth is
unchanged by serialization, observation, synthesis, or playback failure.

At Phase 7 closure, the local CLI was the normal operator surface. Phase 1C workspace/target remains a
specialized legacy mode. The 3090 remains independently sufficient and the 4090
remains optional under unchanged MO2 policy. Future interaction enhancements require
a separately authorized later phase. The subsequently accepted Browser PTT and
Restart GRACI controls are documented above; wake word, VAD, sessions/history,
automatic follow-up, autonomous conversation, generic browser control, new
persistence, and further Phase 8 presence work remain unaccepted.

## Phase 7B local operator CLI integration — COMPLETE

Phase 7A and Phase 7B are complete and accepted by Phase 7C closure.
Ordinary `python -m graci "task"` interaction now enters the accepted Phase 7A
coordinator and its single existing governed `run(task)` submission statement.
`--speech` is one explicit push-to-talk turn: hold Spacebar to capture and release
Spacebar to stop and transcribe; `--speak` is explicit opt-in presentation through
accepted local Kokoro `af_heart`. Typed mode never captures audio and presentation
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

Phase 8A itself added no control. This later authorized capability adds only resident
browser explicit PTT plus a latest validated-response area. All other visualizer state
remains observer-only. `LISTENING` is backend-published only during an accepted hold;
there is no wake word, VAD, continuous listening, automatic follow-up, generic task
submission, routing, memory, or persistence control. The
3090 remains independently sufficient, and optional 4090/MO2 policy is unchanged.
Phase 8B is complete in repository. Phase 8C and later presence work remain unauthorized.
