# Addendum 013 — Architecture 2 Phase 1H Configured Node Inspection and Manual Administration

**Status:** Approved for controlled implementation

**Date:** 2026-08-13

This addendum extends Addendums 011 and 012 and authorizes only explicit inspection of registered Ollama nodes and auditable manual Node administrative-state changes.

## M1. Inspection Boundary

Inspection is explicitly invoked for one registered Architecture 2 Node using caller-resolved configuration and the existing versioned Ollama Model Provider. It may inspect health/version and model inventory. Every attempt records sanitized durable evidence, including partial or failed outcomes.

Inventory snapshots are evidence only. They do not create or qualify providers, capabilities, offerings, models, offering locations, or scheduler eligibility. Inspection never changes Node administrative state, starts work, retries work, or selects a resource.

## M2. Administrative State

The Product Owner or caller may explicitly transition a registered Node among `active`, `draining`, and `disabled`. Each change requires the expected current state, actor, reason, and UTC timestamp. The current projection update, immutable transition history, and Event commit atomically. Stale, invalid, and no-op transitions are rejected.

Draining and disabled Nodes receive no new leases under Addendum 012. State changes do not cancel or rewrite active leases or Attempts.

## M3. Invariants and Acceptance

- Only registered Nodes are inspectable; no endpoint scanning or automatic discovery occurs.
- Configuration and credentials remain caller-owned references and are not persisted in evidence.
- Inspection is bounded, non-periodic, and never runs automatically at startup.
- Inventory ordering is deterministic by model name then digest.
- Health success and inventory presence do not imply qualification.
- Successful, partial, and failed inspection evidence reconstructs identically after restart.
- Schema migration from populated version 5, atomic Event rollback, stale-state rejection, scheduler response to manual state, full regressions, build, configured-node live smoke, Electron startup, and logs must be verified.

## M4. Deferred Boundaries

Phase 1H does not authorize LAN/mDNS/subnet discovery, background polling, automatic endpoint promotion, parallel inspection or execution, automatic drain/reactivation, cancellation/preemption, failover, model deduplication or residency routing, GPU/VRAM/CPU/RAM/process/gaming telemetry, benchmarking, automatic offering creation or qualification, remote workers, cloud nodes, UI redesign, or Architecture 2 Electron authority.
