# GRACI Phase 3E — Resource / Model Router Acceptance & Closure

Phase 3 is formally accepted and complete. The authoritative 3090 is the default
and remains fully functional by itself. The 4090 is optional capacity and is
considered only for an explicit `prefer_optional=True` request.

Every optional dispatch performs a new fixed read-only MO2 query and a new bounded
4090 `/models` query. Exact `ModOrganizer.exe` NOT_RUNNING, enabled resources, a
healthy endpoint, the required model, all policy checks, valid non-future UTC
timestamps, and evidence age no greater than 10 seconds are all required. RUNNING,
UNKNOWN, ERROR, malformed, unreachable, unhealthy, missing-model, stale, or future
evidence fails closed and sends zero 4090 inference requests.

Logical role selection precedes placement: Qwen is implementer/general reasoning;
GLM is reviewer/verifier. Server-reported model identity must exactly match the
requested logical model. An eligible optional request permits at most one 4090
attempt, followed by at most one 3090 attempt after failure. A blocked gate goes
directly to one 3090 attempt. Evidence atomically records role/model, node/endpoint,
eligibility and freshness, attempts and contact counts, fallback, identity, final
outcome, and `cloud_ai_used: false`. Deterministic tests remain authoritative and a
reviewer error or rejection cannot create PASS.

The warning-strict suite passes 107 tests. Final live acceptance record
`0b9d527a-e985-4897-8ce4-aaf77639a7e4.json` proves a local 3090 Qwen
general-reasoning inference and a fresh eligible real 4090 Qwen inference from MO2
NOT_RUNNING state with both models present and exact identities. The sandbox-only
record `2bb8e95e-bdca-4e7a-b279-49c2a0369610.json` records the documented Codex
private-LAN boundary and truthful local fallback. Prior Phase 3D Test A
`1a975f47-55df-4cc5-ad8f-695c6559a78b.json` and Test B
`5f98916a-700f-4c2f-a7c9-3caa288e5abb.json` supply the accepted NOT_RUNNING and
RUNNING transition evidence without repeating manual state changes.

No Phase 3 code exposes arbitrary remote shell/commands, broad process enumeration,
termination, model-controlled eligibility, firewall broadening, secrets, cloud
routing, or shared mutable coordination. The 4090 MO2 service is fixed, read-only,
narrowly firewalled, and reboot persistent. Shared storage is unnecessary for these
small payloads; the repository and durable authority remain on the 3090.

The accepted race is unchanged: MO2 may start after a valid check, and GRACI does
not remotely terminate an already dispatched inference. Subsequent requests recheck
and fail closed. The next authorized phase is Phase 4 — Persistent Memory. Phase 4
has not begun.
