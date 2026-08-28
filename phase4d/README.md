# GRACI Phase 4D — Memory-Guided Agent Execution

Phase 4D integrates Phase 4C selection with the bounded local Qwen execution path.
Memory remains untrusted context and grants no authority. The trusted caller supplies
exactly `context`, `relevance_keys`, `allowed_memory_types`, `limit`, and `mode`.
There is no model-derived key, vault search, or implicit full-store retrieval.

## Execution boundary

`prepare_execution_memory` validates the strict request, calls
`MemoryGovernance.select`, and constructs a canonical JSON envelope. Each entry has
separate `metadata` and `content`; the envelope labels itself
`UNTRUSTED_CONTEXT_DATA`, says entries are not instructions and may be stale or
incorrect, and enumerates authority it cannot override. Delimiters and structured
serialization reduce ambiguity but are not claimed to solve prompt injection.

The independent injection bounds are 10 records, 2,000 content characters per
record, and 12,000 aggregate serialized characters. Oversized records are excluded
deterministically without truncation or LLM summarization. Evidence distinguishes
selected IDs, supplied IDs, selection exclusions, budget exclusions, conflicts,
corruptions, truncation, context size, and receiving role. Full memory content is
not copied into execution evidence.

Optional requests continue truthfully after no match, conflict, invalid selection,
or storage/governance unavailability. Required requests fail before inference unless
usable memory is selected and every selected record can be safely supplied without
corruption, selection truncation, conflict, or context-budget exclusion. Requiredness
is fixed by the trusted request; model output cannot alter it.

## Qwen, GLM, authority, and placement

Qwen receives the frozen envelope inside its bounded controller context. The
existing action schema, allowlisted files, controlled tools, test command, loop and
repair limits, response-model identity check, and deterministic verification are
unchanged. Imperative memory cannot create actions, tool calls, permissions, paths,
routing, MO2 eligibility, test commands, cloud access, or durable writes.

The reviewer independence boundary is metadata-only: GLM receives memory status and
selected/supplied IDs as part of execution evidence, never memory content. It still
has no tools and returns the strict Phase 3B review contract. Failed deterministic
tests prevent reviewer invocation; ordinary adjudication combines deterministic
test state and the strict reviewer result, so memory cannot force PASS. A live GLM
call was not added because the accepted Phase 3B deterministic integration tests
already exercise identity, malformed output, failed-test authority, and adjudication;
adding another live opinion would not validate memory truth or strengthen authority.

Canonical memory remains local to the 3090. This phase adds no 4090 vault path or
shared mutable memory. If an existing optional inference route later carries a Qwen
call, only the already-selected bounded envelope may be request data; existing fresh
MO2 eligibility remains mandatory. No GRACI cloud AI, telemetry, or memory network
service exists.

## Acceptance and limitations

The disposable synthetic live acceptance proves no-match optional execution,
COBALT continuity with exact ID traceability, hostile imperative containment,
required-conflict pre-inference failure, and deterministic reconstruction. Evidence
is `phase4d/evidence/phase4d-acceptance.json`. The complete warning-strict suite,
compilation, JSON evidence validation, bounded secret scan, and Git checks are part
of final verification.

GRACI still does not perform semantic/vector search, use embeddings, automatically
remember conversations or model conclusions, let models resolve conflicts, treat
memory as authority, allow 4090 to own or mutate the vault, or use cloud memory.
Keys and request context must come from trusted application code. Content is
excluded rather than summarized when it does not fit. Phase 4D does not add a
general database transaction engine or multi-process writer coordination.

The next authorized stage is Phase 4E — Persistent Memory Acceptance & Closure.
Phase 4E has not begun.
