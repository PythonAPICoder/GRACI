# GRACI Phase 4E — Persistent Memory Acceptance and Closure

Phase 4E accepts the complete Phase 4 subsystem. Canonical memory is local UTF-8
JSON on a host-selected, 3090-authoritative root. Schema v1 remains readable; schema
v2 adds exact relevance, expiration, and supersession metadata. Governance never
invents missing v2 fields for v1 records.

Durable writes require an explicit trusted path. GRACI forces provenance, canonical
UUID/timestamps/status/version, rejects caller metadata injection and bounded obvious
secrets, and uses operation-based UUIDv5 idempotency. Ordinary conversation is not
persisted. Retrieval and selection are exact, deterministic, bounded, and diagnostic;
there is no semantic search, fuzzy matching, embedding, or model conflict resolution.

Scope is explicit. A session composes session, its named project, and global records
only through caller-set flags, in specificity order session → project → global.
Supersession retains history and retires the prior record. Trusted host time excludes
expired records without read mutation. Ambiguous active same-key records are diagnosed
and excluded rather than resolved by provenance or timestamps.

Execution memory is caller-requested and optional or required. Selected content enters
a deterministic `UNTRUSTED_CONTEXT_DATA` envelope with metadata separated. Limits are
10 records, 2,000 content characters per record, and 12,000 serialized characters;
oversized entries are excluded truthfully, never LLM-summarized. Required failure stops
before inference. Qwen may see bounded content, but tools, paths, tests, budgets,
routing, MO2, and deterministic acceptance remain unchanged. GLM receives status/ID
metadata only, not content. Existing Phase 3B/4D tests prove malformed-output,
identity, failed-test, and adjudication behavior, so no additional live GLM call was
performed.

Corrupt records are excluded with diagnostics. Imperative, system-like, tool-like,
routing, reviewer, cloud, path, and shell-looking content remains inert data. The 4090
neither owns nor mutates the vault and still requires fresh Phase 3 eligibility for
optional inference. Shared storage remains intentionally unused. Obsidian is not a
runtime dependency; derived Markdown views may not bypass governed JSON writes. No
GRACI cloud AI, cloud memory, memory telemetry, or memory-bearing service is used.

Intentional limitations: no semantic/vector search, embeddings, automatic conversation
capture, unrestricted autonomous learning, model conflict resolution, comprehensive
secret detection, Obsidian canonical editing, or cross-machine canonical-memory
synchronization. These are deliberate boundaries, not forgotten defects.

Run `python phase4e/run_acceptance.py`. Inspect
`phase4e/evidence/phase4e-closure.json` for durable IDs, lifecycle/conflict/corruption
diagnostics, context sizes, precondition model-call counts, server identity, authority,
and privacy evidence.

**PHASE 4 — PERSISTENT MEMORY COMPLETE.** The next authorized phase is Phase 5 —
Visualizer. Phase 5 has not begun.
