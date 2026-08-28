# GRACI Phase 3C — 4090 Availability & MO2 Policy

Phase 3C adds a read-only eligibility signal for the optional 4090. It does not
route or execute inference there. The 3090 remains the authoritative node used by
the Phase 3B role router.

## MO2 detector

The 4090 runs a startup Scheduled Task named `GRACI MO2 Read-Only Status` as
`SYSTEM`. Its PowerShell `HttpListener` serves only `GET /graci/v1/mo2` on TCP
8765. A local CIM filter selects only `Name = 'ModOrganizer.exe'`, and an
ordinal-ignore-case comparison implements Windows process-name semantics. The
response contains only schema version 1, exact process name, state, and reason.
States are `RUNNING`, `NOT_RUNNING`, and `ERROR`.

The Windows Firewall inbound rule `GRACI MO2 Status from 3090` is restricted to
local address `192.168.0.101`, remote address `192.168.0.100`, and TCP port 8765.
No WinRM, remote WMI, PowerShell remoting, general command endpoint, process
termination, or service-control API was enabled. The initial program-scoped rule
was corrected because `HttpListener` ingress is owned by HTTP.sys (PID 4), not the
PowerShell process. Application-level caller validation also permits only the 3090
address and loopback.

The installed endpoint source is preserved for audit at
`windows/mo2-status.ps1`; it contains no credential or secret. The Scheduled Task
uses its installed copy at `C:\ProgramData\GRACI\mo2-status.ps1`.

`graci.availability.check_4090_mo2_status` can contact only the fixed status URL,
uses GET with no request body, enforces a bounded timeout and 4 KiB response limit,
validates exact keys/identity/state/reason combinations, and returns explicit
RUNNING, NOT_RUNNING, UNKNOWN, or ERROR results. Timeout, authentication,
transport, HTTP, malformed, oversized, identity-mismatched, or contradictory
responses never become NOT_RUNNING.

## Eligibility and precedence

`evaluate_4090_eligibility` is a pure decision function and has no provider or
dispatch interface. Its deterministic precedence is:

1. `node_disabled`
2. `mo2_running`
3. `mo2_state_unknown`
4. `mo2_query_error`
5. `endpoint_unknown`
6. `endpoint_unhealthy`
7. `required_model_unavailable`
8. `policy_blocked`
9. `eligible`

Eligibility requires the optional node enabled, a definitive MO2 NOT_RUNNING
result, healthy schema-valid `/models` evidence, the required model observed and
enabled, consistent fixed registry references, and all applicable policy checks.
Endpoint health never overrides MO2. The existing Phase 3B router still resolves
Qwen and GLM only on the 3090, so this signal cannot dispatch a workload.

## Verification and evidence

The warning-strict suite passes 86 tests: all 75 Phase 1/2/3A/3B regressions plus
11 Phase 3C tests. Coverage includes exact found/absent behavior, timeout,
authentication and network errors, malformed/empty/contradictory responses,
similar names, documented Windows case semantics, fixed GET-only contact, every
eligibility state and precedence, MO2 overriding healthy/unhealthy endpoints, and
3090 routing independence.

Real Test A evidence is
`evidence/c60baa4e-db7c-441c-b57d-877ee5e5e1e8.json`. It observed exact
`ModOrganizer.exe` NOT_RUNNING, HTTP 200 from the 4090 `/models` endpoint, both
registered models, required Qwen available, and eligibility `eligible`.

Real Test B evidence is
`evidence/ffa32f4c-7077-4075-bf62-9e8f4e95ced8.json`. It observed exact
`ModOrganizer.exe` RUNNING while `/models` remained healthy and both models
remained available. Eligibility was false with `mo2_running`, proving endpoint
health cannot override the gate. The user selected a closed final desktop state,
and a subsequent independent query observed NOT_RUNNING.

Both evidence records enumerate only two network operations: the fixed MO2 GET
and `/v1/models` GET. Each records zero inference requests and no cloud AI. No
password, token, API key, credential, or authentication material is stored.

## Security boundary and limitations

The detector is read-only, exact-name-only, timeout-bounded, response-bounded, and
fail-closed. Models receive no status-query tool and cannot select a process, URL,
state, policy, or reason. There is no inference provider for the 4090, and the
primary router is unchanged. The endpoint exposes one process-presence bit in
unencrypted HTTP on the trusted LAN; source/destination/port firewall restriction
and application caller restriction are therefore required. If the task, listener,
firewall, host, LAN, or response becomes unavailable or uncertain, the 4090 is
ineligible while the 3090 remains unaffected.

Phase 3D — Distributed Routing / Failover is next and has not begun.
