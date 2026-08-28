# GRACI Phase 4B — Governed Memory Write / Retrieval Pipeline

Phase 4B builds explicit ingress and deterministic exact retrieval on the accepted
Phase 4A JSON store. Memory is untrusted context, never authority. It cannot execute
tools, authorize filesystem or repository changes, alter MO2/security/routing policy,
select memory roots, authorize 4090/cloud use, or establish PASS. Current explicit
instructions, deterministic policy, verified runtime state, and test evidence outrank it.

## Write contract and authorization

`MemoryPipeline` exposes four distinct capability entry points. Trusted user requests
force `explicit_user`; trusted deterministic runtime observations force
`runtime_observation`; model proposals force `model_generated`; trusted imports force
`imported_external`. The strict request contains exactly `operation_id`, `scope`,
`memory_type`, `content`, and bounded `source_ref`. Caller-supplied provenance,
`memory_id`, timestamps, status, schema version, or record version is rejected.
Ordinary controller/task text has no connection to these methods, so no conversation
or apparently useful text is silently persisted.

Content is preserved verbatim as inert UTF-8 text after non-empty, 16,384-byte, scope,
type, provenance-source, and accepted Phase 4A bounded secret checks. Markdown, HTML,
code, and instruction-like wording acquire no semantics. Rejections expose reason
codes, not submitted content. The defense recognizes obvious credential assignments
and private-key blocks; it is not comprehensive secret detection.

Idempotency is operational, not semantic. A canonical operation UUID plus the fixed
capability path deterministically derives a UUIDv5 memory ID. An identical authorized
retry returns `IDEMPOTENT_REPLAY` and the existing record. A changed payload under the
same operation returns `IDEMPOTENCY_CONFLICT`; a distinct operation creates a distinct
record even for identical content. This survives restart without a second mutable index.

## Retrieval contract

Retrieval requires an exact explicit scope and supports exact `memory_id`, scope,
memory type, provenance origin, lifecycle status, and inclusive created/updated lower
and upper time bounds. Omitted status becomes `active`; superseded, expired, and
tombstoned records require an explicit status. There is no implicit scope composition.

The canonical order is `updated_at` descending, then `created_at` descending, then
`memory_id` ascending. The default result limit is 25 and hard maximum is 100; invalid
limits fail closed. At most 1,000 UUID-ordered canonical candidates are inspected and
scan/result truncation is reported. Valid records are returned alongside bounded Phase
4A corruption diagnostics; corrupt and unsupported records never become usable results.
Results and diagnostics are structured, serializable, and do not expose storage paths.

No content query, fuzzy matching, relevance scoring, semantic/vector search, embedding,
model inference, network, or cloud facility exists. Retrieved data is not injected into
Qwen, GLM, autonomous agents, or tool flows.

## Security, interoperability, and limitations

The host selects the absolute root and the 3090 remains sole authority. There is no
shared-drive or 4090 mutation/replication dependency. A future immutable export/backup
may be evaluated separately. JSON remains canonical; Obsidian can later consume a
derived view but cannot edit around this pipeline and is not a runtime dependency.

Phase 4B intentionally does not provide automatic conversation extraction, “remember
everything,” semantic relevance/ranking, conflict or supersession resolution, expiration
governance, lifecycle automation, scope merging, autonomous prompt injection, or
cross-machine/cloud memory. Those boundaries are not errors. Phase 4C may next address
Relevance, Scope & Supersession; it has not begun.

The warning-strict suite passes 150 tests, including 22 focused Phase 4B tests and all
128 Phase 1–4A regressions. `phase4b/evidence/phase4b-acceptance.json` records the bounded
synthetic local acceptance, provenance rejection, idempotent replay, distinct operation,
exact bounded retrieval, reconstruction, corruption exclusion, and no-semantic-search
proof. No cloud AI or 4090 was used.
