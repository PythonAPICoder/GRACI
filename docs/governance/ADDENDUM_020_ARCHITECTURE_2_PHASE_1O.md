# Addendum 020 - Architecture 2 Phase 1O Scoped Circuit Breakers and Bound Probes

**Status:** Approved for controlled implementation

**Date:** 2026-08-14

This addendum extends Addendums 005 through 019 and supersedes only the prior deferment of circuit breakers and half-open probes. It authorizes the bounded caller-invoked behavior below. Every other Phase 1N deferral and all earlier deferrals not expressly changed here remain in force.

## T1. Authorized Scope and States

Phase 1O authorizes independent circuit breakers for exactly three target categories:

- one provider offering;
- one registered Node;
- one offering location.

Each circuit has the explicit states `closed`, `open`, and `half_open`. A circuit is independent from circuits at other scopes, including circuits that happen to affect the same execution route. Circuit state is trusted routing policy state, not provider health, qualification, Node administrative state, or offering-location enablement.

Phase 1O is caller-invoked. It introduces no startup polling, background monitor, automatic health mutation, automatic Node administration, or scheduler-owned probe creation.

## T2. Versioned Policy and Qualifying Evidence

Every circuit stores an immutable policy identity/version and the exact positive integer observation window, failure threshold, cooldown, and qualifying category set used to create it. A later request cannot silently reinterpret an existing circuit under different policy metadata. Policy evolution requires explicit versioned behavior; migration must not fabricate evidence under a new policy.

Only a current trusted Phase 1L diagnosis may count as failure evidence. It must use the current trusted diagnosis policy/version, have outcome certainty `proven_unsuccessful`, attribute the exact circuit target, and classify the cause in the circuit policy's explicit qualifying set. The initial Phase 1O policy may qualify only:

- `transient_infrastructure`;
- `resource_unavailable`;
- `provider_or_capability_mismatch`;
- `execution_defect`.

The following categories are explicitly excluded and cannot open or reopen a circuit: `invalid_input_or_precondition`, `policy_or_approval`, `verification_failure`, `external_outcome_indeterminate`, `cancelled_or_preempted`, and `unknown`. Stale, superseded, malformed, contradictory, non-current, unattributed, or insufficient diagnosis evidence also cannot count.

## T3. Deterministic Window and Cooldown

Failure counting uses diagnosis timestamps as canonical UTC evidence time. The evidence timestamp must equal the authoritative diagnosis timestamp and cannot predate its Failure. For an observation at time `t`, only qualifying evidence for the same circuit with timestamps in the inclusive deterministic interval `[t - observationWindowMs, t]` counts. Evidence outside that interval does not contribute.

A `closed` circuit opens only when the configured threshold is reached. Opening records `openedAt` and computes `cooldownUntil` deterministically as `openedAt + cooldownMs`. Before that instant the route is rejected as open. At or after that instant ordinary routing remains rejected and exactly one probe authority may move the circuit to `half_open`; elapsed cooldown alone does not close or bypass the circuit.

## T4. Durable One-at-a-Time Probe Authority

A probe is immutable durable authority with `active`, `claimed`, and `consumed` status. Acquisition atomically records the probe, audit Events, and `open -> half_open` transition. A circuit may have only one active probe, and while half-open it cannot grant another probe.

Only the exact active probe identity may pass the affected circuit filter. Provider resolution and resource scheduling must otherwise record stable circuit rejection reasons. Probe authority is consumable once: trusted core must durably claim it before Attempt start, and a claimed or consumed probe cannot be reused by another resolution, scheduling decision, Task, or Attempt.

## T5. Exact Attempt and Route Binding

A claim binds the probe to the exact Task ID, Attempt ID, Attempt number, provider offering, and, where applicable, Node and offering location. A provider-offering probe also requires the exact persisted provider-resolution decision that selected that offering while carrying the probe identity. A Node or offering-location probe requires the exact persisted resource-scheduling decision carrying the probe identity and selecting the bound Node/location; location probes additionally retain the normal matching durable lease relationship.

Attempt start must atomically validate that the claimed probe, Task, Attempt identity/number, provider offering, and compute binding match. Mismatch, missing routing authority, stale status, reuse, or unprovable correspondence fails closed. A probe does not reserve capacity, expand eligibility beyond its exact target, waive qualification or health requirements, or bypass privacy, permission, approval, Attempt-limit, lease, or other routing gates.

## T6. Probe Outcomes

Only a persisted normal passing Verification for the exact successful bound probe Attempt may consume the probe and transition `half_open -> closed`. Attempt success, provider self-report, health evidence, routing success, lease release, or an unrelated Verification cannot close a circuit.

A current qualifying Phase 1L diagnosis for the exact failed bound probe Attempt may consume the probe and transition `half_open -> open`. Reopening starts a new deterministic cooldown from the transition timestamp. A non-qualifying failure, Verification rejection, indeterminate outcome, unknown cause, malformed attribution, or unrelated diagnosis supplies no close or replay authority and must fail closed.

Provider output remains evidence only. Circuit behavior cannot mark a Task successful, replace normal Verification, infer an external outcome, or rewrite an Attempt.

## T7. Routing Explanations and Metadata Separation

Provider resolution must expose stable `circuit_open` and `circuit_probe_required` rejection reasons. Resource scheduling must expose scope-specific `node_circuit_open`, `node_circuit_probe_required`, `location_circuit_open`, and `location_circuit_probe_required` reasons. Existing deterministic candidate ordering and all other rejection reasons remain authoritative.

Circuit records, evidence, transitions, and probes are separate metadata. They must not mutate or masquerade as provider health, qualification, Node health, Node administrative state, offering-location enablement, workstation evidence, lease state, or Failure diagnosis. Existing metadata remains independently inspectable and authoritative for its own purpose.

## T8. Persistence, Concurrency, and Recovery

Schema version 12 stores circuit projections, immutable qualifying evidence, immutable transitions, and durable probe history with foreign keys to authoritative diagnoses, routing/resource decisions, Verifications, and Events. State transitions, probe acquisition/claim/consumption, and their Events commit transactionally. Optimistic circuit versions, SQLite write serialization, conditional status updates, and uniqueness constraints enforce one-at-a-time authority under concurrent callers.

Close/reopen reconstruction must preserve exact target, policy, state, timing, evidence, transition, probe, claim, route, Attempt, outcome, and Event relationships. Direct update or deletion of immutable evidence and transitions is rejected. Malformed state or relationships produce explicit diagnostics rather than inferred availability.

Restart does not replay or replace an active or claimed probe. A circuit that cannot prove a safe current state remains unavailable pending explicit trusted handling. Circuit authority never becomes general recovery authority.

## T9. No Replay, Replacement, or Unknown-Outcome Authority

Phase 1O authorizes no replay, replacement Attempt, alternative offering, alternative Node, reconciliation conclusion, retry-budget reset, approval bypass, checkpoint resume, migration, cancellation, replanning, research, or provider installation. It only filters routes and permits one exact bound probe Attempt through already-governed execution paths.

The Phase 1N invariant remains absolute: **Unknown means stop.** An indeterminate external outcome cannot count as qualifying circuit evidence, authorize or claim a probe, close or reopen a circuit as a known probe result, or be replayed, rerouted, retried, migrated, replaced, or treated as successful.

## T10. Acceptance Requirements

Controlled implementation must verify independent provider-offering, Node, and offering-location circuits; explicit excluded categories; deterministic inclusive windows and cooldown; stable open/probe-required routing explanations; one active durable probe under concurrency; exact provider/resource decision, lease, Task, Attempt, offering, Node, and location binding; atomic one-time claim and Attempt-start validation; passing-Verification-only close; qualifying bound-failure reopen; unrelated Verification/diagnosis rejection; metadata separation; no replay or replacement authority; unknown-outcome stop behavior; schema-11 to schema-12 migration without fabricated circuits; immutable history and SQLite close/reopen reconstruction; prior Phase 1L through Phase 1N regressions; TypeScript validation; complete tests; production build; runtime/import checks; Electron startup regression; diff hygiene; and engineering-log and living-document updates.

## T11. Deferred Boundaries

Phase 1O does not authorize background or automatic failure observation, automatic probe scheduling, startup probing, continuous health polling, adaptive thresholds, dynamic policy replacement, bulk target circuits, cancellation/preemption, checkpointing, live migration, interrupted-work failover, automatic alternative recovery, input revision, planning/replanning, Task Graph mutation, governed research, web/model research, automatic installation, distributed workers, multiple Orchestrators, generalized policy-engine redesign, generalized tool execution, memory, UI work, or Electron Architecture 2 authority cutover.

All Phase 1N deferred boundaries and all earlier deferrals remain preserved except the circuit-breaker and half-open-probe deferment expressly superseded by this addendum.
