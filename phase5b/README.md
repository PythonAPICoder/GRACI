# Phase 5B — Local Visualizer Backend

Phase 5B transports the accepted immutable Phase 5A projection to a future same-origin
browser UI. It is optional: GRACI core does not import or depend on the HTTP server.
The standard-library server binds only `127.0.0.1:8766`; non-loopback hosts are
rejected at construction and port conflicts fail without fallback.

API version 1 exposes only:

- `GET|HEAD /graci/visualizer/v1/health`
- `GET|HEAD /graci/visualizer/v1/snapshot`
- `GET|HEAD /graci/visualizer/v1/events`
- `GET|HEAD /graci/visualizer/v1/events/stream` (`GET` is SSE)

Before trusted runtime publication, health remains `200` with
`snapshot_available:false`; snapshot returns bounded `503 snapshot_unavailable`.
Snapshots use `serialize_visualizer` directly. Recent events are oldest-to-newest and
retain Phase 5A's last 100 only.

SSE frames contain `id`, Phase 5A event type, and deterministic JSON data. A known
`Last-Event-ID` replays retained later events. An unknown/evicted ID replays the
currently retained buffer. Invalid IDs fail closed. Heartbeats are comments every 15
seconds and never domain events. At most eight streams may be live. Streams read the
shared bounded buffer after condition notification, so publication never writes to a
client and keeps only one event cursor rather than a per-client queue; a disconnected or slow client cannot
block GRACI and reconnects from snapshot/recent events.

All write/tunnel methods are `405` and have no side effects. Request bodies, queries,
malformed/traversal-like targets, oversized request targets, and non-local Host values
are rejected. CORS headers are absent. Responses use `Cache-Control: no-store`,
`X-Content-Type-Options: nosniff`, and `Referrer-Policy: no-referrer`. Internal
`VisualizerStateProvider.publish_*` methods accept already-validated immutable Phase
5A objects; no HTTP route reaches them.

The backend imports no provider, tools, memory writer, router, MO2 probe, inference,
filesystem, subprocess, cloud, or 4090 capability. It cannot submit/change tasks,
execute tools, mutate memory/repository/routing/review, authorize the 4090, bypass
MO2, trigger inference, approve work, upload files, change configuration, or stop the
server over HTTP. Shutdown is an internal lifecycle operation only.

Run the bounded synthetic acceptance with `python -m phase5b.run_acceptance`. Durable
evidence is written to `phase5b/evidence/phase5b-acceptance.json`.

Phase 5B does not implement the command-center UI, task submission, controls, remote
access, voice, a WebSocket/control channel, static-file serving, or any cloud service.
Static trusted same-origin UI serving is deferred to Phase 5C; no arbitrary filesystem
root or directory listing exists. Host validation is defense in depth, not a substitute
for loopback binding. Header-count/size enforcement otherwise uses Python's bounded
HTTP parser. Recent events are display state, not durable audit evidence.

Next authorized stage after acceptance: Phase 5C — Command-Center UI.
