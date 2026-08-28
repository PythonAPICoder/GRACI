# Phase 5A — Visualizer State Contract

Phase 5A adds the trusted internal contract for a future GRACI visualizer. It is an
observer-only projection, not a user interface or controller.

## Architecture and authority

Dependency direction is strictly one-way:

`authoritative runtime/domain/evidence -> graci.visualizer projector -> immutable snapshot/events -> future backend -> future UI`

Core runtime modules do not import the visualizer. `graci.visualizer` performs no
network probing, model inference, file writes, tool execution, memory access,
routing, review approval, or task submission. It accepts typed trusted facts and
returns immutable display objects. Runtime and durable audit evidence remain
authoritative. Model output cannot directly declare terminal completion; completion
requires a deterministic terminal fact, and deterministic test failure always
projects as failure.

## Contracts

Snapshot schema version 1 contains `snapshot_id`, timezone-aware `generated_at`,
derived `system_state`, task, fixed compute topology, distinct Qwen/GLM activity,
governed memory metadata, recent operations/tests, review/adjudication state, and
recent events. Missing facts use explicit null, `unknown`, or `not_applicable`
semantics.

System states are `idle`, `listening`, `planning`, `retrieving_memory`, `reasoning`,
`executing_tool`, `testing`, `reviewing`, `adjudicating`, `completed`, `warning`,
`failed`, and `speaking`. Listening and speaking are vocabulary reservations for
Phase 6; Phase 5A implements no voice capability.

Event schema version 1 uses strict event-type and severity enums. Severities are
`info`, `activity`, `success`, `warning`, and `error`. Events are frozen, ordered by
timezone-aware timestamp, reject duplicate IDs and future/out-of-order insertion,
and live in an oldest-first-evicted recent buffer capped at 100. This buffer is not
durable audit storage.

## Bounds and minimization

- task summary: 240 characters
- event message: 320 characters
- error/failure/policy summary: 240 characters
- target/display label: 160 characters
- event metadata: 16 sorted JSON-scalar entries; keys 64 and string values 160 characters
- recent operations: 25
- recent events: 100

Projection deliberately excludes full prompts, memory contents, vault data, hidden
chain-of-thought/reviewer rationale, arbitrary file contents, raw stdout/stderr,
environment dumps, credentials, and tokens. This is architectural minimization plus
a narrow secret-looking metadata-key rejection, not comprehensive DLP.

The 3090 is always represented as primary authority. The 4090 is optional capacity
and mirrors already-established endpoint, eligibility, policy, and MO2 facts. MO2
`RUNNING` forces the displayed 4090 state to unavailable/ineligible but grants no
control. Qwen and GLM have separate typed activity views; GLM review output remains
separate from deterministic adjudication. Memory exposes only request mode,
relevance keys, selection status, IDs, counts, context size, and diagnostics.

## Acceptance and limitations

`python -m phase5a.run_acceptance` constructs an offline synthetic lifecycle from
idle through memory, Qwen, tool use, tests, GLM review, adjudication, and completion.
It also covers eligible and MO2-blocked 4090 state, optional memory absence, required
memory conflict, deterministic test failure, and task failure. No cloud AI or real
model inference is used.

Phase 5A does **not** implement a browser UI, CSS/animation, HTTP or WebSocket
server, controls/task submission, voice/STT/TTS, or remote visualizer access. The
next authorized stage after acceptance is Phase 5B — Local Visualizer Backend.
