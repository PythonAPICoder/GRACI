# GRACI Phase 4C — Relevance, Scope, and Supersession

Phase 4C adds a deterministic selection boundary over the accepted local Phase
4A/4B store. Memory remains inert context, never authority. This phase performs no
prompt construction, model inference, semantic search, routing, tool execution,
network access, or autonomous memory consumption.

## Schema and migration decision

Governed records use schema version 2 and add exactly three fields:
`relevance_key`, nullable timezone-aware `expires_at`, and nullable canonical UUID
`supersedes_memory_id`. Schema-v1 records remain strictly readable in their accepted
shape. They are not rewritten or silently assigned a key; selection excludes them
with `NO_RELEVANCE_METADATA`. Unsupported or malformed records remain corruption
diagnostics. This is deterministic backward compatibility without reinterpretation.

Relevance keys are inert canonical lowercase dotted segments. Each segment begins
with an ASCII lowercase letter or digit and may continue with lowercase letters,
digits, `_`, or `-`; total length is 1–128 characters. There is no case folding,
path mapping, executable meaning, similarity comparison, fuzzy grouping, embedding,
or model-derived key. A request supplies 1–50 unique exact keys.

## Scope identity and composition decision

The accepted scope representation remains `{kind, id}`. Global requires null `id`;
project and session require exact validated identifiers. Selection requires an
explicit context with `kind`, `project_id`, `session_id`, `include_global`, and
`include_project`; there is no current-scope guessing.

- Global context accepts only global memory and cannot enable narrower scopes.
- Project context accepts its exact project. Global is eligible only when
  `include_global=true`. Session memory never applies.
- Session context accepts its exact session. Its exact parent project is eligible
  only when `include_project=true`; global is eligible only when
  `include_global=true`.
- Unrelated project and session identifiers never apply.

Specificity is `session > project > global`. For a requested relevance-key/type
group, only candidates at the highest applicable specificity are considered.
Lower candidates receive `LESS_SPECIFIC_SCOPE`. Specificity is an applicability
rule, not truth or authority; it does not override current instructions or runtime
evidence.

## Supersession, expiration, and conflicts

Replacement is an explicit provenance-forcing governed operation. The prior record
must be active schema-v2 memory with the exact same scope, relevance key, and memory
type. The replacement points to the prior UUID, is published as a new record, and
the prior record is retained with `superseded` status and incremented version.
Self-reference, mismatches, and relationship cycles fail closed. UUIDv5 operation
idempotency makes exact retries stable; changed retries conflict. If retiring the
prior record fails, the unpublished replacement half is removed and the prior
remains active. Selection also treats a valid explicit replacement edge as retired,
so a partial active pair cannot silently appear authoritative.

Expiration is computed during selection from nullable `expires_at` using only the
host-configured timezone-aware store clock. `expires_at <= current time` is excluded
with `EXPIRED_AT_READ`; reads do not mutate durable status. Selection requests have
no time field, so model output cannot control current time.

After lifecycle, exact-key/type, applicability, and explicit replacement handling,
multiple active candidates at the winning scope are an ambiguity. No timestamp,
version, content, or provenance class is treated as truth. Every candidate is
excluded and an `AMBIGUOUS_ACTIVE_CANDIDATES` diagnostic lists sorted UUIDs. Retired
or expired records do not create conflicts. Different keys never conflict merely
because their text resembles or duplicates one another.

## Governed selection API and bounds

`MemoryGovernance.select` accepts exactly an explicit context, relevance-key list,
optional allowed memory-type list, and result limit. It returns usable canonical
records, per-selected-record applicability explanations, exclusion reason codes,
conflict diagnostics, corruption diagnostics, ordering, counts, scan bounds, and
truthful truncation. It emits no prompt strings.

Ordering is scope specificity descending, `updated_at` descending, `created_at`
descending, then `memory_id` ascending. The default/result hard limits remain 25
and 100; at most 1,000 store entries are scanned; at most 50 keys are requested.
Scan or result truncation is explicit. Content is never parsed or executed.

Provenance records origin only. It has no universal precedence and does not resolve
ambiguity. Memory cannot override current user instructions, deterministic policy,
verified runtime evidence, tests, MO2 rules, routing, filesystem boundaries, cloud
policy, or acceptance status.

## Development, test, and failure record

Starting commit `0747e14f4bfcf3d0eb8ac3a487df80e64ad7a476`
and a clean authoritative `E:\GRACI` tree were verified before work. Focused tests
cover strict keys and scopes, composition/isolation, schema-v1 compatibility,
replacement/history/retry/rollback/cycles, trusted-clock expiration, conflicts,
provenance non-authority, deterministic reconstruction, ordering, bounds,
corruption, path containment, instruction-like content, and absence of network or
routing dependencies.

The bounded disposable live acceptance proves global/project/session isolation,
explicit session composition, historical supersession, expiration exclusion,
controlled ambiguous candidates, deterministic reconstruction, and inert imperative
text. Durable evidence is `phase4c/evidence/phase4c-acceptance.json`.

The focused implementation pass found and fixed replacement-retry handling: an
already-retired target now permits only exact UUIDv5 replacement replay and rejects
new or changed replacements. No accepted security boundary was weakened. Final
warning-strict regression, compilation, evidence validation, secret scan, and Git
checks are recorded in the evidence and project state.

## Known limitations and next stage

GRACI still does not semantically search memory, use embeddings, infer relevance
from free text, automatically extract conversation memory, let models resolve
conflicts, inject memory into prompts, or allow agents to consume memory. There is
no cloud memory, cross-machine synchronization, or 4090 authority. Multi-record
replacement uses fail-safe rollback and relationship-aware selection, not a general
database transaction engine; concurrent multi-process writers are not introduced
or supported in Phase 4C.

Phase 4C stops at governed selection. The next authorized stage is Phase 4D —
Memory-Guided Agent Execution. Phase 4D has not begun.
