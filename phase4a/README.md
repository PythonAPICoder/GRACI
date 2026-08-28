# GRACI Phase 4A — Memory Data Model & Storage

Phase 4A establishes storage only. Memory supplies potentially stale or incorrect
context and never grants authority. Explicit user instructions, tool/security/MO2/
routing/repository policy, deterministic evidence, and current verified runtime
state always take precedence. Content—including instruction-like or malicious
text—is inert data in this phase; no model receives or controls it.

## Canonical record and taxonomy

Canonical memory is one human-inspectable UTF-8 JSON object per record using exact
schema version 1 fields: `schema_version`, canonical lowercase UUID `memory_id`,
timezone-aware `created_at` and `updated_at`, explicit `scope`, `memory_type`,
non-empty string `content`, `provenance`, `status`, and positive integer `version`.
Malformed timestamps and `updated_at < created_at` are rejected, never repaired.

Scope is exactly `{kind, id}`. `global` requires a null id; `project` and `session`
require a bounded identifier. The deliberately small extensible type taxonomy is
`fact`, `preference`, `decision`, `context`, and `workflow`. Lifecycle status is
`active`, `superseded`, `expired`, or `tombstoned`; retirement is logical, not
physical deletion. Provenance is exactly `{origin, source_ref}` and distinguishes
`explicit_user`, `runtime_observation`, `model_generated`, and `imported_external`.
It is attribution, not proof or authority, and model-generated content gains no
privilege.

## Storage, atomicity, and failures

`graci.memory.MemoryStore` accepts an absolute host-selected root and derives only
`<uuid>.json` paths beneath it. Callers cannot select extensions, directories, or
arbitrary paths through the memory API. Creation uses an fsynced same-directory
temporary plus atomic hard-link publication (collision cannot overwrite). Updates
validate the complete result, preserve identity/creation time, increment version,
advance update time, and atomically replace from an fsynced temporary. Interrupted
replacement preserves the prior record. Temporary artifacts are not canonical.

Retrieval validates JSON, exact fields, schema, identity, timestamps, scope, type,
provenance, status, content, and version. Enumeration is UUID-filename ordered,
offset/limit bounded (default 100, maximum 1000), and follows option B: valid records
are returned with explicit corruption diagnostics. Corrupt records are never in the
usable record collection. Missing files, malformed/truncated content, collisions,
and filesystem errors fail truthfully.

The store rejects obvious private-key blocks and simple credential assignments as a
bounded defense, not comprehensive secret detection. Callers must not submit API
keys, passwords, tokens, private keys, credentials, or environment/config secrets.
No cloud, network, database, vector, embedding, provider, Qwen, GLM, or 4090 runtime
dependency exists.

## Authority and interoperability decisions

The default deployment target is an authoritative local 3090 directory. Phase 4A
does not create shared mutable state, replicate to the 4090, or permit 4090 writes.
Future phases may assess immutable exports or backups. The one-record-per-file JSON
layout is friendly to later generated Markdown views, but Obsidian is not a runtime
dependency and Markdown is not canonical metadata. No plugin is introduced.

Known limitations: no automatic extraction/write, semantic search, embeddings,
ranking, prompt injection, autonomous consumption, supersession/expiry engine,
cross-machine sync, cloud storage, historical version archive, comprehensive secret
detection, or index. Concurrent updates are atomic but do not yet expose optimistic
version preconditions. Those pipeline concerns are outside 4A.

The 128 automated warning-strict tests cover schema/storage/security/failure behavior
and all Phase 1–3 regressions. `phase4a/evidence/phase4a-acceptance.json` records bounded
local live creation, retrieval, deterministic enumeration, reconstructed-store
persistence, update, corruption rejection, boundary enforcement, and atomicity.
The next authorized stage is Phase 4B — Memory Write / Retrieval Pipeline; it has
not begun.
