# Addendum 010 — Architecture 2 Phase 1E Runtime Composition and Legacy-State Import Boundary

**Status:** Approved for controlled implementation

**Date:** 2026-08-13

This addendum extends Addendums 005 through 009 and authorizes only the explicit Architecture 2 runtime composition and non-destructive Architecture 1 state assessment/import boundary described below.

## J1. Runtime Composition Boundary

Architecture 2 shall expose one explicit composition boundary that constructs caller-configured SQLite persistence, the existing sequential Orchestrator, dependency evaluation, deterministic scheduler, execution-provider contract, verifier, and queue inspection/reconstruction services.

Database paths and replaceable execution components are supplied explicitly. Architecture 2 core remains independent of Electron and contains no machine-specific path. Composition does not make Architecture 2 the normal Electron authority; Architecture 1 remains active by default.

## J2. Legacy State Is Untrusted Compatibility Input

Architecture 1 `graci_state.json` is a read-only compatibility source, never authoritative Architecture 2 state. Assessment reads the supplied source without using Architecture 1's caching or fallback behavior and never creates, rewrites, renames, deletes, or normalizes the source file.

Assessment results classify every discovered top-level section or record as `importable`, `unsupported`, `ambiguous`, or `malformed`, with stable reason codes and source provenance. Malformed JSON, invalid root shape, unsupported sections, and incomplete records remain explicit. Identical source bytes produce the same digest, record ordering, classifications, and reasons.

## J3. Authorized Import Semantics

Phase 1E may preserve only well-formed Architecture 1 Task records as non-canonical legacy history with their original payload and lifecycle label. A Task is importable only when its key is non-empty and its value is an object containing a matching non-empty `id`, a non-empty `type`, a recognized Architecture 1 status, and a finite non-negative numeric `createdAt`. Optional lifecycle timestamps must also be finite non-negative numbers when present; optional error text must be a string.

Architecture 1 registry sections are assessed but remain `unsupported`. They are not imported into Architecture 2 provider, model, node, tool, capability, health, or qualification records. Unknown top-level sections are unsupported.

Imported legacy history is not a Goal, canonical Task, Attempt, Verification, Approval, dependency, graph, provider, capability, or qualification. It is never scheduler-eligible and cannot affect Architecture 2 lifecycle state.

## J4. No Fabricated Evidence

Architecture 1 lifecycle labels are retained only as source history. In particular, Architecture 1 `completed` does not become Architecture 2 `succeeded`. Phase 1E must not infer or create Attempts, Verifications, approvals, dependencies, graph history, execution success, qualification, provider health, or other evidence absent from the source.

Missing semantics are classified as ambiguous or unsupported rather than guessed. Later promotion of legacy history into canonical workflow state requires separately governed semantics and evidence.

## J5. Idempotency and Provenance

Every assessment records the SHA-256 digest of the exact source bytes and the caller-supplied source reference. Every imported history record retains the source digest, source reference, Architecture 1 section and key, original payload, assessment contract version, and import timestamp.

The durable store enforces uniqueness by source digest, source section, and source key. Repeating an import of identical bytes creates no duplicate history records. Import is transactional and records one durable import operation even when no records are eligible. Import timestamps and operation identifiers are operational metadata and do not alter deterministic assessment results.

## J6. Bootstrap and Reconstruction

A configured runtime initializes and migrates a real SQLite database, exposes controlled Architecture 2 workflow and inspection operations, performs explicit legacy assessment/import only when called, closes cleanly, and reconstructs durable canonical and legacy-history state after reopen.

No automatic legacy import occurs during bootstrap. No imported legacy record is automatically executed.

## J7. Deferred Boundaries

Phase 1E does not authorize capability/provider registries, real model or provider integration, Ollama/vLLM/OpenAI/Gemini integration, qualification, model/node selection, GPU or multi-node scheduling, concurrent or parallel execution, remote workers, dynamic planning, additional predicate behavior, cloud behavior, autonomous installation, Electron UI redesign, or Architecture 2 becoming the default Electron runtime.

Slice 2 and Phase 1F remain deferred. Speculative abstractions created solely for later phases remain prohibited.
