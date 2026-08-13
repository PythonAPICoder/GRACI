# Addendum 008 — Architecture 2 Phase 1C Failure Policy

**Status:** Approved for controlled implementation

**Date:** 2026-08-13

This addendum extends Addendums 005 through 007 and authorizes the smallest persistence-backed Phase 1C policy extension.

## H1. Failure Classification

Every execution or verification failure carries one machine-readable classification: `transient`, `permanent`, `verification_failed`, `approval_required`, or `external_outcome_indeterminate`. Existing diagnostic categories remain supplemental detail.

## H2. Retry Policy

Automatic retry is finite and requires both explicit classification eligibility and remaining budget. The default is three total Attempts. `transient` is retryable by default. `verification_failed` is retryable only when the Task explicitly opts in. `permanent`, `approval_required`, and `external_outcome_indeterminate` are never automatically retried. Attempt history and budget derive from durable records and survive restart.

Recovery from `retry_pending` must revalidate the latest relevant durable Failure, its retryable decision, classification eligibility, and remaining Attempt budget before returning a Task to `ready`. Unprovable retry authorization fails closed. When migrating pre-Phase-1C Failures, only retryable `transient_infrastructure` is classified `transient`; ambiguous resource and policy categories remain `permanent`, while verification and indeterminate categories retain their provable semantics.

## H3. Approval Lifecycle

`approval_required` atomically ends the current Attempt, records the Failure and Approval request, and transitions the Task to `waiting_for_approval`. Recovery leaves that state paused. Explicit approval durably records the decision before returning the same Task to `ready`; denial records its reason and terminally fails the Task. Invalid approval transitions are rejected.

## H4. Safety and Scope

Phase 1B interrupted-attempt recovery remains unchanged: an uncertain external outcome is recorded as `external_outcome_indeterminate`, becomes terminally failed, and is never replayed. Phase 1C introduces no real providers, routing, UI, scheduling, network API, or generalized recovery system.
