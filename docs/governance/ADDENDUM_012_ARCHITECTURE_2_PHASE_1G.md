# Addendum 012 — Architecture 2 Phase 1G Durable Node Binding and Resource Leases

**Status:** Approved for controlled implementation

**Date:** 2026-08-13

This addendum extends Addendums 002, 005, and 011 and authorizes only the smallest durable Architecture 2 Slice 3 node-binding and resource-lease kernel.

## L1. Purpose

Phase 1G adds the second routing stage after provider-offering resolution:

```text
qualified provider offering -> eligible configured node/location -> durable decision and lease
  -> Attempt bound to offering and node -> invocation -> lease release
```

Architecture 2 remains caller-configured and disconnected from normal Electron startup. Architecture 1 remains authoritative.

## L2. Authorized Records and Operations

Phase 1G authorizes stable logical Node records, offering locations, append-only node health observations, deterministic scheduling decisions, and time-bounded resource leases. Nodes have explicit `active`, `draining`, or `disabled` administrative state. Offering locations identify where an already-qualified provider offering can execute; they do not duplicate or imply capability, model, or qualification records.

Registration, observation, decision, lease acquisition, release, and reconciliation are transactional and emit append-only Events. Configuration references may identify caller-managed endpoint configuration, but credentials and endpoint secrets must not be persisted in canonical records, Events, Failures, or logs.

## L3. Deterministic Eligibility and Ranking

A location is eligible only when its node and location are enabled, the node is active, current health evidence exists and is fresh, privacy/residency constraints permit execution, declared capacity is sufficient after active leases, and all records are structurally valid.

Eligible candidates rank deterministically by acceptable health, available capacity descending, observation time descending, Node ID lexical ascending, then location ID lexical ascending. Missing, stale, degraded, unhealthy, unknown, draining, disabled, privacy-incompatible, or capacity-exhausted state fails closed with stable reasons. Phase 1G does not guess GPU performance, model residency, network latency, workload, or gaming state.

## L4. Lease and Invocation Invariants

1. Provider-offering selection and node selection are separate durable decisions.
2. Scheduling decision, active lease, Task transition to `scheduled`, and corresponding Events commit atomically where workflow scheduling occurs.
3. A provider invocation requires a valid active lease and matching offering/location/node binding.
4. The Attempt records the exact offering and Node before invocation.
5. Known completion or failure releases the lease. Lease history is retained.
6. Draining prevents new leases but does not cancel active work.
7. Expiry does not prove that an external effect did not occur.
8. Interrupted scheduled/running work preserves the existing fail-closed, no-blind-replay behavior.
9. Architecture 1 and imported legacy node records never become Architecture 2 nodes automatically.
10. Task queue ordering remains the Phase 1D sequential `createdAt`, then Task-ID order.

## L5. Acceptance Requirements

Controlled implementation must verify schema-version-4 migration with populated data; atomic registration/Event rollback; deterministic close/reopen reconstruction; malformed-state diagnostics; stable filtering/ranking across insertion order and restart; stale, unhealthy, draining, disabled, privacy, and capacity rejection; lease conflict prevention; matching Attempt offering/Node identity before invocation; release on known outcomes; expired lease reconciliation without replay; all Phase 1A through 1F regressions; TypeScript validation; production build; real SQLite reopen; configured-node inspection when available; Electron startup regression; diff hygiene; and engineering-log updates.

No new dependency is authorized unless environment inspection proves it necessary and a separately recorded decision approves it.

## L6. Deferred Boundaries

Phase 1G does not authorize automatic network discovery or endpoint promotion, GPU/VRAM/CPU/RAM/process telemetry, model-location deduplication, model residency routing, measured performance learning, gaming or Mod Organizer 2 detection, automatic drain policy, concurrent execution, priority queue reordering, cancellation/preemption/checkpoint migration, automatic failover or alternative-node retry, remote workers, distributed consensus, cloud nodes, generalized policy, dynamic planning, UI redesign, Architecture 1 promotion/deletion, or Architecture 2 becoming the default Electron runtime.
