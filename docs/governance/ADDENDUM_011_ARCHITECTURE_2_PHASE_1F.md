# Addendum 011 — Architecture 2 Phase 1F Capability and Provider Resolution

**Status:** Approved for controlled implementation

**Date:** 2026-08-13

This addendum extends Addendums 005 through 010 and authorizes only the durable capability/provider resolution boundary and one qualified Ollama Model Provider adapter described below.

## K1. Phase 1F Purpose

Phase 1F begins Architecture 2 Slice 2. It introduces versioned provider contracts, durable capability and provider-offering records, qualification and health evidence, deterministic policy-filtered resolution, durable routing explanations, and an Ollama adapter behind the Model Provider boundary.

Architecture 2 remains caller-configured and disconnected from normal Electron startup. Architecture 1 remains the active application authority.

## K2. Canonical Provider and Capability Records

Architecture 2 shall distinguish:

- a provider adapter identity and version;
- a stable capability and compatible contract version;
- a provider offering of that capability;
- a model identity, when the offering is model-backed;
- qualification evidence and its validity period;
- health observations and their freshness;
- a resolution request, considered candidates, decision, and explanation.

These records are Architecture 2 records. Architecture 1 registry entries and imported legacy history do not become providers, capabilities, offerings, qualifications, models, or health evidence.

Provider configuration uses caller-supplied references. Credentials and secrets must not be persisted in provider, capability, offering, qualification, health, routing, Failure, Event, or log payloads.

## K3. Qualification and Health

An offering is resolver-eligible only when the required capability and contract version match, qualification is current and sufficient for the requested workload, and health evidence satisfies the configured freshness requirement.

Availability, a successful health check, model inventory presence, a provider name, or a model description is not qualification. Qualification requires durable task-specific evidence. Records must represent at least qualified, expired, rejected, and not-yet-qualified outcomes without guessing missing evidence.

Material adapter, provider, model, quantization, runtime, prompt-contract, or hardware changes invalidate or trigger requalification as defined by the recorded qualification policy.

Health observations are append-only historical facts. A current projection may be rebuilt from them. Missing, stale, malformed, or contradictory evidence fails closed and produces an explicit diagnostic.

## K4. Deterministic Policy-Filtered Resolution

Resolution starts from a Task's required capability IDs and caller-supplied constraints. It filters candidates by:

- capability and contract-version compatibility;
- current qualification and health;
- privacy and data-destination constraints;
- required permissions and side-effect class;
- input/output schema and supported-format compatibility;
- required features;
- explicit quality, latency, and cost limits represented by the request.

The resolver shall use an explicit stable ranking and tie-break order independent of database, filesystem, object, Map, Set, network, or provider response iteration order. Every decision records the request, metadata versions, candidates considered, stable rejection reasons, selected offering when one exists, and the final explanation.

Resolution cannot silently weaken privacy, permission, contract, qualification, or quality requirements. If no eligible offering exists, resolution fails closed with a structured `provider_or_capability_mismatch` diagnosis.

Phase 1F accepts caller-supplied policy constraints; it does not introduce the generalized Policy Engine or standing-policy UX.

## K5. Orchestration and Persistence Boundary

The selected provider offering must be durably recorded before provider invocation. The Attempt records the exact offering selected. A provider registry/factory may bind that durable offering to a caller-supplied adapter instance, but runtime adapter objects are not authoritative durable state.

Provider, capability, offering, qualification, health, and routing-decision writes use transactional persistence and corresponding append-only Events. Schema migration, reconstruction, deterministic queries, referential integrity, uniqueness, immutable historical evidence, and explicit corruption diagnostics follow the existing Architecture 2 persistence rules.

Provider output remains untrusted execution evidence. It cannot transition a Task to `succeeded`; the existing independent Verification requirement remains authoritative. Retry, approval, dependency, queue, and interrupted-outcome behavior from Addendums 007 through 010 remains unchanged. An uncertain provider outcome is never blindly replayed.

## K6. Ollama Model Provider Adapter

Phase 1F may adapt the existing Ollama support behind a replaceable, versioned Model Provider boundary. The adapter shall use explicit caller-supplied endpoint and timeout configuration and provide only:

- health and version inspection;
- model inventory inspection;
- bounded non-streaming text generation for an explicitly selected qualified model offering;
- structural response validation;
- normalized success, retryable failure, non-retryable failure, and indeterminate-outcome results.

The Architecture 2 adapter core must not depend on the Architecture 1 singleton service, global registry instances, or machine-specific default configuration. Discovery or health success does not automatically register or qualify an offering. Live integration verification may use a configured Ollama endpoint, but an unavailable endpoint must be reported as unavailable rather than simulated as successful.

## K7. Acceptance Requirements

Controlled implementation must verify:

- transactional migration from schema version 3 with populated-state regression coverage;
- atomic registration plus Event writes and complete rollback on failure;
- deterministic close/reopen reconstruction and explicit malformed-state diagnostics;
- qualification expiry, rejection, freshness, requalification triggers, and fail-closed missing evidence;
- stable candidate filtering, rejection reasons, ranking, and tie-breaking across input permutations and restart;
- privacy, permission, contract, feature, format, quality, latency, and cost constraint enforcement where represented;
- durable routing explanations and selected-offering identity before invocation;
- provider exception and resolver failure normalization into durable Failures;
- verification authority, bounded retry, approval, queue, dependency, and interrupted-recovery regressions;
- Ollama health, inventory, generation, timeout, malformed-response, HTTP-error, and connection-failure contract tests;
- live Ollama smoke verification when a configured node is available;
- TypeScript validation, full automated regression tests, production build, real SQLite reopen verification, Electron startup regression smoke, diff hygiene, and repository-artifact inspection.

No new dependency is authorized unless existing environment inspection proves it necessary and a separately recorded decision approves it.

## K8. Deferred Boundaries

Phase 1F does not authorize automatic network discovery, node registry implementation, model-location deduplication across nodes, GPU/VRAM inspection, model residency routing, resource leases, concurrent execution, parallel scheduling, preemption, draining, node failover, distributed consensus, cloud providers, remote workers, autonomous installation, automatic qualification from names or availability, a generalized Policy Engine, approval UI, dynamic planning or replanning, predicate execution, governed research, generalized alternative selection, streaming, chat memory, tool calling, embeddings, vision, multimodal behavior, Architecture 1 registry promotion, legacy-history promotion, UI redesign, Architecture 1 deletion, or Architecture 2 becoming the default Electron runtime.

Those capabilities require later governed phases in the dependency order established by Addendum 005 E17.
