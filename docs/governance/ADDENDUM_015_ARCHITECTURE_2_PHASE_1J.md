# Addendum 015 — Architecture 2 Phase 1J Workstation Availability Policy Application

**Status:** Approved for controlled implementation

**Date:** 2026-08-13

This addendum extends Addendums 012 through 014 and authorizes only explicit, evidence-linked application of one durable Phase 1I workstation availability recommendation to its registered Node.

## O1. Application Boundary

Phase 1J exposes a caller-invoked policy operation. It accepts one exact persisted Phase 1I evaluation, expected rule fingerprint, explicit evidence-freshness bound, expected Node administrative state and version, policy identity/version, actor, reason, and UTC application time.

The operation may map fresh valid `recommend_draining` evidence from `active` to `draining`, or fresh valid `recommend_active` evidence from `draining` to `active`. `inconclusive` evidence, disabled Nodes, malformed or stale evidence, mismatched Nodes or fingerprints, superseded evidence, and stale Node state/version never change administrative state.

## O2. Ownership and Concurrency

Policy-driven administrative transitions are durably linked to their immutable policy-application record. Reactivation is permitted only when the current draining state and version were produced by the same policy identity/version. Current state alone never proves ownership. A manual or other intervening administrative transition changes the Node version and invalidates stale application or reversal.

Every request requires exact expected durable Node state and version. Mismatch fails closed and is recorded. Repeating the same application identity and command returns the original immutable decision and creates no duplicate transition; conflicting reuse of an application identity is rejected.

## O3. Durability and Atomicity

Schema version 8 adds append-only workstation-availability policy applications referencing the exact Phase 1I evaluation and Node. Each record includes application, evidence, policy, actor, reason, expected and observed Node state/version, recommendation, bounded disposition, transition/result details, Event reference, and UTC timestamp.

Every accepted invocation records an immutable application decision, including rejected and no-change outcomes. When a transition occurs, the decision, Node projection update, administrative transition history, and audit Event commit in one transaction. Failure of any write rolls back all participating state. Corrupt references, dispositions, timestamps, versions, or transition relationships produce explicit diagnostics.

## O4. Scheduler and Privacy Invariants

Phase 1J relies on the existing scheduler exclusion of draining and disabled Nodes. It does not modify or cancel active leases or Attempts, preempt work, migrate work, checkpoint work, unload models, or redesign scheduling. Scheduling never captures process evidence or invokes this policy.

Application records and Events contain only bounded evidence identifiers and policy metadata. Process command lines, arguments, usernames, credentials, secrets, endpoint details, and unrelated workstation metadata remain prohibited.

## O5. Deferred Boundaries

Phase 1J does not authorize polling, background or startup application, scheduler-triggered evaluation/application, remote inspection, process control, fuzzy or contextual process inference, game-library discovery, MO2 profile inspection, hardware/performance telemetry, cancellation, preemption, migration, failover, concurrency redesign, automatic offering or location creation, model residency management, UI work, Electron startup integration, Architecture 2 authority cutover, generalized policy-engine infrastructure, or speculative Phase 1K behavior.
