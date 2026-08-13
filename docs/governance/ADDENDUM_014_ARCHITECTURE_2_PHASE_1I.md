# Addendum 014 — Architecture 2 Phase 1I Caller-Invoked Workstation Availability Evaluation

**Status:** Approved for controlled implementation

**Date:** 2026-08-13

This addendum extends Addendums 012 and 013 and authorizes only caller-invoked Windows process snapshots and deterministic workstation availability recommendations.

## N1. Evaluation Boundary

Phase 1I may capture one bounded, read-only Windows process snapshot for one registered Node and evaluate caller-supplied, versioned exact executable-basename rules. Initial rules may identify Mod Organizer 2 and explicitly configured game executables.

The result is `recommend_draining`, `recommend_active`, or `inconclusive`. Recommendations are durable evidence, not administrative authority. Applying `draining` or `active` requires a separate explicit Node transition under Addendum 013.

## N2. Safety and Privacy

- Evaluation is explicit and non-periodic; no startup or background watcher is authorized.
- The adapter invokes a fixed executable with fixed arguments without a shell.
- Timeout and output-size limits are mandatory.
- Only executable basenames and rule identifiers may be persisted. Command lines, arguments, environment, usernames, window titles, and secrets are prohibited.
- Matching is case-insensitive exact basename matching after Windows normalization.
- Any blocking match recommends draining. A complete no-match snapshot recommends active. Failure, malformed/truncated output, unsupported platform, or unprovable completeness is inconclusive.
- Evaluation cannot mutate Nodes, leases, Tasks, providers, offerings, qualifications, or scheduler state.

## N3. Acceptance and Deferred Boundaries

Implementation must verify complete/empty/failed/malformed/truncated snapshots, Mod Organizer aliases, configured games, deterministic ordering across permutations, schema migration from populated version 6, atomic Event rollback, restart reconstruction, recommendation/state separation, scheduler regressions, live Windows snapshot, full tests, build, Electron startup, diff hygiene, and logs.

Phase 1I does not authorize automatic drain/reactivation, polling, scheduler-triggered evaluation, process control, fuzzy/window/foreground/parent-process inference, game-library discovery, MO2 profile inspection, hardware telemetry, remote process inspection, concurrent execution, preemption, failover, UI work, or Architecture 2 Electron authority.
