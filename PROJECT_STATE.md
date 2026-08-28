# GRACI Project State

## Current build status

- Phase 5 — COMPLETE
- Phase 6 — IN PROGRESS
- Phase 6A — COMPLETE
- Phase 6B — COMPLETE
- Phase 6C — COMPLETE
- Phase 6D — COMPLETE
- Phase 6E — COMPLETE
- **Phase 6 — COMPLETE AT BOUNDED PUSH-TO-TALK VOICE INTERACTION**
- Phase 6B authoritative starting commit: `291240f623bd73957f4afc84a6adb61c9ce3fdae`.
- Phase 6 interaction model: push-to-talk. Always-listening and wake word are deferred.
- Phase 6B adds explicit push-to-talk, dependency-free Windows PCM capture, typed
  lifecycle/results, and fully local faster-whisper `small.en` CPU `int8` through an
  isolated local-only worker. Audio is transient by default; no runtime submission,
  TTS coupling, background listening, cloud, or 4090 dependency was added.
- Phase 6B focused tests pass 16/16; the full warning-strict suite passes 278/278.
  The concrete local worker transcribed a tracked synthetic WAV from the existing
  cache. A real microphone smoke test remains optional and was not run.
- Phase 6C passes successful nonblank transcripts unchanged to the existing governed
  `run(task)` boundary and adds no separate speech authority.
- Phase 6D accepts only an explicit immutable authoritative final-response value,
  derives the Phase 6A speech-only pronunciation copy, synthesizes through local
  Kokoro-82M ONNX CPU `af_bella`, validates bounded WAV output, and plays through a
  bounded stoppable subprocess. Presentation failures never alter governed results.
- Phase 6D focused tests pass 21/21; the complete warning-strict suite passes 307/307.
  Live cached Kokoro synthesis passed; physical speaker playback was not performed.
- Phase 6E reuses canonical `idle`, `listening`, and `speaking` system states through
  a replaceable observer-only publisher. Guarded leases wrap the actual bounded Phase
  6B capture/recognition span and Phase 6D playback call, restore idle on every exit,
  reject overlap/late restoration, and isolate recorded publisher failures from all
  authoritative and presentation results. Phase 6E focused tests pass 8/8; the full
  warning-strict suite passes 315/315. No physical microphone/speaker test was run.
- Integrated Phase 6 closure composes the accepted 6B–6E interfaces in deterministic
  tests without a production coordinator: explicit capture and local transcription,
  exactly one ordinary governed submission for one accepted transcript, an independent
  governed result, explicit authoritative-response construction, optional bounded
  synthesis/playback, and observer-only lifecycle publication. Phase 6 closure adds
  no autonomous loop, execution path, authority, scheduling, network, or persistence.
  Consolidated evidence is `phase6/evidence/phase6-closure.json`.
- No Phase 6F is named or authorized. Wake word, VAD, continuous listening, automatic
  reopening/submission/speech loops, turn-taking, duplex, expanded interruption,
  UI/device work, fallback engines, network/cloud/distributed speech, GPU/4090 voice
  routing, scheduling changes, and persistence remain deferred pending separate
  roadmap authorization.
- Phase 6A voice decision: Kokoro-82M ONNX `af_bella` is the preferred production candidate. A bounded speech-only lexicon pronounces the unchanged written tokens `GRACI`, `3090`, and `4090` as `GRAY-see`, `thirty ninety`, and `forty ninety`; unrelated numbers are not rewritten.
- Evidence: `phase6a/evidence/phase6a-qualification.json`; architecture and reconstruction: `phase6a/ARCHITECTURE.md` and `phase6a/README.md`.

## Phase 5C command-center UI — COMPLETE

- Starting commit: `7a12d4c42a9ac1951c47653ce11048c2da346df8`.
- `http://127.0.0.1:8766/` now serves packaged HTML/CSS/vanilla JavaScript/SVG with no build step or external runtime.
- The 3440x1440-first layout separates compute/agents, a state-reactive abstract core, current task/memory/review/adjudication, a six-stage pipeline, operations, and bounded SSE events. Geometry checks at 2560x1440 and 1920x1080 found no horizontal overflow.
- Same-origin serving is a three-path allowlist under `graci/visualizer_ui`, not a repository web root. Decoded traversal is rejected, assets are bounded, directory listing is unavailable, MIME types are fixed, and CSP is self-only.
- Snapshots refresh every 3000 ms; EventSource events are deduplicated and DOM-bounded at 100. Disconnect preserves last-known data and truthfully marks transport DISCONNECTED / STALE.
- `phase5c.synthetic` exercises the lifecycle, warning/failure, and both 4090 available and MO2-blocked truth without an HTTP mutator or core-runtime dependency.
- Semantic regions, labels, non-color state text, and reduced-motion behavior provide accessibility basics.
- Evidence: `phase5c/evidence/phase5c-acceptance.json`; details: `phase5c/README.md`.
- No controls, runtime publication wiring, voice, remote access, cloud, memory/routing mutation, or inference were added.
- Next authorized stage: Phase 5D — Live Runtime Integration. Phase 5D has not begun.

## Phase 5B local visualizer backend — COMPLETE

- Starting commit `213e88972041916bd38c413f91a9babfc1663fe6` and clean
  authoritative `E:\GRACI` state were verified before modification.
- `graci.visualizer_backend` is an optional standard-library HTTP/SSE transport over
  trusted immutable Phase 5A objects. It binds only `127.0.0.1`, defaults to port
  `8766`, exposes API v1 health/snapshot/events/event-stream GET/HEAD endpoints, and
  never becomes a GRACI core dependency.
- The provider synchronizes atomic snapshot reads/publication and Phase 5A's ordered
  100-event immutable buffer. SSE supports eight clients, bounded retained replay,
  strict `Last-Event-ID`, comment heartbeats, and no per-client accumulation or
  publisher writes to clients.
- Startup health is truthful while snapshot returns 503 until trusted publication.
  CORS is absent; local Host validation, no-store/nosniff/no-referrer headers,
  request-target/body/path checks, deterministic bounded errors, and GET/HEAD-only
  policy preserve the loopback observer boundary.
- There is no task/tool/memory/repository/routing/MO2/reviewer/inference/configuration/
  shutdown/cloud control endpoint. Phase 5B implements no UI, voice, remote access,
  WebSocket, static filesystem serving, or cloud service. Phase 5C remains unstarted.
- Real local acceptance on `127.0.0.1:8766` passed idle/active exact snapshots,
  eligible and MO2-blocked display state, eight ordered synthetic lifecycle events,
  write/mutation rejection without side effects, internal shutdown, and port release.
  The complete warning-strict suite passes 231 tests including Phase 5A and Phase 1–4
  regressions. Compilation, JSON evidence validation, bounded secret scan, and Git
  whitespace validation pass. Durable evidence is
  `phase5b/evidence/phase5b-acceptance.json`.
- Next authorized stage: Phase 5C — Command-Center UI. It has not begun.

## Phase 5A visualizer state contract — COMPLETE

- Starting commit `7ddf51c7fd55fd9e2f4c5fee74a8c18445f40bb3` and a clean
  authoritative repository were verified before modification.
- `graci.visualizer` defines immutable snapshot schema v1 and event schema v1 as a
  pure projection of typed, trusted runtime facts. Dependency direction is
  authoritative runtime/domain/evidence -> visualizer projection -> immutable
  snapshot/events -> future backend/UI. Core modules do not depend on it.
- System states are idle, listening, planning, retrieving_memory, reasoning,
  executing_tool, testing, reviewing, adjudicating, completed, warning, failed,
  and speaking. Listening/speaking reserve Phase 6 vocabulary only. Deterministic
  failure wins, and completion requires deterministic terminal support rather than
  a model claim.
- The fixed compute view preserves the 3090 as primary authority and the 4090 as
  optional capacity. It mirrors endpoint/eligibility/MO2 facts without probing or
  changing policy; MO2 RUNNING displays the 4090 unavailable and ineligible.
  Qwen/GLM activity is separate, memory is metadata-only, raw tool output is
  excluded, and reviewer verdict remains separate from deterministic adjudication.
- Recent immutable events use strict event-type and severity enums, reject duplicate
  IDs plus future/out-of-order insertion, and evict oldest-first at 100 entries.
  Bounds are 240 characters for task/error summaries, 320 for event messages, 160
  for display labels, 16 bounded scalar metadata entries, and 25 operations.
- Architectural minimization excludes full prompts, memory/vault content, arbitrary
  files, raw stdout/stderr, environment dumps, credentials/tokens, and hidden
  chain-of-thought/reviewer rationale. Narrow secret-key rejection is not claimed as
  comprehensive DLP. The contract has no tool, memory mutation, routing, approval,
  task submission, network, provider, filesystem-write, or canonical-state capability.
- Offline synthetic acceptance covers idle through task/memory/Qwen/tool/tests/GLM/
  adjudication/completion, eligible and MO2-blocked 4090 state, optional memory
  absence, required memory conflict, deterministic test failure, task failure,
  serialization, source immutability, and bounded event eviction. Durable evidence
  is `phase5a/evidence/phase5a-acceptance.json`; no model inference or cloud AI is used.
- Phase 5A implements no browser UI, HTTP/WebSocket server, controls/task submission,
  voice, or remote visualizer access. Next authorized stage: Phase 5B — Local
  Visualizer Backend. It has not begun.

## Phase 4C relevance, scope, and supersession — COMPLETE

- Starting commit `0747e14f4bfcf3d0eb8ac3a487df80e64ad7a476` and a clean
  authoritative `E:\GRACI` tree were verified before modification.
- New governed records use schema v2 with exact `relevance_key`, nullable
  timezone-aware `expires_at`, and nullable canonical `supersedes_memory_id`.
  Schema-v1 records remain readable without rewriting or reinterpretation and are
  excluded from governed selection with `NO_RELEVANCE_METADATA`.
- Relevance is exact only: 1–128 character canonical lowercase dotted keys, at most
  50 unique requested keys, no semantics, fuzzy matching, embeddings, path meaning,
  or model inference. Project and session scopes retain exact bounded identity.
- Callers provide explicit global/project/session context and composition flags.
  Matching specificity is session > project > global; parent project and global
  inclusion are explicit. Unrelated projects and sessions never apply.
- Explicit governed replacement requires equal scope/key/type, preserves the old
  record as `superseded`, records the relationship, rejects cycles/self-reference,
  rolls back on retirement failure, and preserves UUIDv5 retry idempotency.
- Expiration is computed at selection from the host clock without read-time writes.
  Retired and expired candidates are excluded. Same-key/type active ambiguity at
  the winning scope is diagnosed and all ambiguous records are excluded; provenance,
  timestamps, and model judgment do not choose truth.
- `MemoryGovernance.select` returns selected records, applicability explanations,
  exclusion/conflict/corruption diagnostics, deterministic ordering, bounds, and
  truncation. Ordering is specificity descending, updated/created time descending,
  then UUID ascending. Limits are 25 default, 100 hard, 1,000 scanned.
- The complete warning-strict suite passes 174 tests, including all Phase 1–4B
  regressions. Disposable local acceptance and fresh-object reconstruction pass.
  Evidence and full architecture/development/test/failure notes are under
  `phase4c/`. No GRACI cloud AI or 4090 dependency was used or introduced.
- Memory remains inert context, not authority. GRACI still has no semantic memory
  search, embeddings, free-text relevance, model conflict resolution, prompt
  injection, or autonomous memory consumption.
- Next authorized stage: Phase 4D — Memory-Guided Agent Execution. It has not begun.

## Phase 4B memory write / retrieval pipeline — COMPLETE

- Starting commit `e472fe948637f18422aa75b49df235b55d9fa741` was verified
  exactly with a clean authoritative `E:\GRACI` working tree before modification.
- `graci.memory_pipeline.MemoryPipeline` provides four explicit governed write
  capabilities. Trusted user, trusted deterministic runtime, model proposal, and
  trusted import paths force `explicit_user`, `runtime_observation`,
  `model_generated`, and `imported_external` respectively. Caller prose cannot
  claim stronger provenance, and ordinary controller/task text is never persisted.
- The exact write request contains only operation UUID, scope, type, content, and
  source reference. GRACI assigns UUID, timestamps, active status, schema version,
  and initial version. Empty or over-16,384-byte content, metadata injection, and
  accepted Phase 4A obvious-secret patterns fail closed without content echo.
- Operational idempotency derives a UUIDv5 from capability plus operation UUID.
  Identical retries resolve to the existing record, changed retry payloads conflict,
  and distinct operations remain distinct even with identical text. Semantics are
  not compared.
- Retrieval requires explicit exact scope and supports exact ID, type, provenance,
  status, and inclusive created/updated time bounds. Status defaults to active.
  Ordering is updated time descending, created time descending, then UUID ascending.
  Results default to 25, reject limits over 100, inspect at most 1,000 candidates,
  and explicitly report truncation and Phase 4A corruption diagnostics.
- Memory stays inert, untrusted context. It grants no tool, filesystem, repository,
  routing, MO2, security, cloud, 4090, or acceptance authority and is not injected
  into Qwen/GLM/agent prompts. There is no network/provider dependency.
- JSON on the local 3090 remains canonical. No shared-drive/4090 replication or
  mutation and no Obsidian runtime/edit path was introduced. Future immutable
  export/backup may be evaluated separately.
- The complete warning-strict suite passes 150 tests: 22 focused Phase 4B tests and
  all 128 Phase 1–4A regressions. Bounded synthetic live acceptance, idempotency,
  exact retrieval, fresh-instance reconstruction, and corruption exclusion pass.
  Durable details are in `phase4b/README.md` and
  `phase4b/evidence/phase4b-acceptance.json`; no cloud AI or 4090 was used.
- Phase 4B still does not implement semantic relevance/search, embeddings, automatic
  conversation extraction, conflict/supersession resolution, expiration governance,
  implicit scope composition, or autonomous prompt injection.
- Next authorized stage: Phase 4C — Relevance, Scope & Supersession. It has not begun.

## Phase 4A persistent memory storage — COMPLETE

- Canonical schema-v1 UTF-8 JSON records live one per canonical UUID filename under
  an absolute host-configured root. Strict validation covers exact fields, stable
  identity, timezone-aware/logically ordered timestamps, explicit scope/type/status/
  provenance, non-empty content, and positive versions.
- Scope kinds are global/project/session; types are fact/preference/decision/context/
  workflow; statuses are active/superseded/expired/tombstoned; provenance origins
  distinguish explicit user, runtime observation, model generation, and external
  import without conferring truth or authority.
- Create publication and updates use fsynced same-directory temporaries with atomic
  filesystem operations. Duplicate IDs fail closed; updates preserve identity and
  creation time while incrementing version. Retrieval always revalidates canonical
  content. Bounded deterministic enumeration returns valid records plus explicit
  corruption diagnostics, never corruption as usable context.
- Paths derive only from validated UUIDs beneath the host-selected root. No arbitrary
  extension/path access exists. Bounded obvious-secret patterns are rejected, while
  documentation explicitly disclaims comprehensive secret detection. Malicious or
  instruction-like content remains inert data.
- The 3090 local filesystem remains authoritative. There is no shared-drive mutable
  state, 4090 mutation/replication, cloud/network/provider dependency, Obsidian
  runtime/plugin, Markdown authority, automatic extraction/write, embeddings,
  semantic search, ranking, conflict engine, or model prompt injection.
- Phase 4A architecture, security decisions, limitations, acceptance, development
  record, test record, and failure behavior are documented in `phase4a/README.md`.
  Durable acceptance is `phase4a/evidence/phase4a-acceptance.json`.
- The next authorized stage is Phase 4B — Memory Write / Retrieval Pipeline. It has
  not begun.

This document and the durable files in this repository are the authoritative source of GRACI project state. Conversation history is not project state.

## Project and phase

GRACI is a local-first AI workload orchestration project. It will coordinate inference resources while preserving safe availability rules and the ability to operate entirely on the primary host.

## Build progress

- Overall Build: Phase 3 complete
- Completed Phases: Phase 1 — Minimal GRACI Core; Phase 2 — Autonomous Loop; Phase 3 — Resource / Model Router
- Current Phase: Phase 3E — Resource / Model Router Acceptance & Closure, complete
- Completed Stages: Phase 3A — Resource & Endpoint Registry; Phase 3B — Local Model Role Routing; Phase 3C — 4090 Availability & MO2 Policy; Phase 3D — Distributed Routing / Failover; Phase 3E — Acceptance & Closure
- Next Authorized Phase: Phase 4 — Persistent Memory

Phase 1A through Phase 1D and Phase 2A through Phase 2C are accepted. Phase 2 is
implemented, verified, closed, and committed by the closure commit containing this
state. Phase 3A through Phase 3E are implemented, verified, accepted, and closed.

## Phase 3E acceptance and closure

- Starting commit `fe2ea4980a206d176dd41208cb6ed67507f56fd5` was verified
  exactly with a clean authoritative `E:\GRACI` working tree before any change.
- Integrated acceptance found and repaired two narrow Phase 3 gaps: the registry's
  advertised Qwen `general_reasoning` role is now routable, and routing evidence now
  includes explicit per-node inference contact counts in addition to attempts and
  contact booleans. No architecture was redesigned.
- The warning-strict suite passes 107 tests, including all Phase 1, Phase 2, and
  Phase 3 regressions plus eight focused Phase 3E integration tests. Coverage
  includes topology, 3090-only use, all role mappings, explicit optional placement,
  fresh checks, every fail-closed gate, bounded fallback, identity mismatch,
  reviewer/adjudication authority, atomic evidence, security boundaries, prior live
  evidence validation, and zero cloud routing.
- Final live acceptance `0b9d527a-e985-4897-8ce4-aaf77639a7e4` passed from the
  expected state. It proved one 3090 general-reasoning Qwen inference and one real
  explicitly optional 4090 Qwen inference; MO2 was exactly NOT_RUNNING, both models
  were present, evidence was fresh, identities matched, and contact counts were
  exactly one local and one remote across the two bounded operations. The initial
  Codex sandbox run `2bb8e95e-bdca-4e7a-b279-49c2a0369610` truthfully failed closed
  on private-LAN access and fell back to the healthy 3090; the unchanged runner then
  passed in the normal authoritative-host network context.
- Prior Phase 3D records `1a975f47-55df-4cc5-ad8f-695c6559a78b` (NOT_RUNNING,
  eligible real 4090 inference) and `5f98916a-700f-4c2f-a7c9-3caa288e5abb`
  (RUNNING, zero remote inference, successful 3090 fallback) remain incorporated.
- Security review found no arbitrary remote shell or command execution, broad
  process enumeration, process termination, model-controlled policy, firewall
  broadening, secret persistence, cloud routing, or shared mutable coordination.
  The 4090 support service remains read-only, narrowly firewalled, and reboot
  persistent. The authoritative repository and evidence remain 3090-only.
- Shared storage remains unnecessary for bounded Phase 3 prompts, responses, health
  observations, and JSON evidence. A future phase may use it only where materially
  useful and never as an eligibility authority.
- The accepted race remains: MO2 can start after a valid check and an already
  dispatched inference is not remotely terminated. Every subsequent optional
  dispatch performs fresh checks and fails closed. The Codex private-LAN sandbox
  boundary is not a GRACI defect and did not cause any firewall or policy change.

## Phase 3D distributed routing and failover

- `graci.distributed.Phase3DDistributedRouter` preserves Phase 3B role selection:
  Qwen is implementer/general reasoning and GLM is reviewer/verifier. Endpoint
  placement happens afterward and cannot substitute a model.
- The deterministic default is the authoritative 3090. Only explicit
  `prefer_optional=True` requests consider the 4090. Each new optional dispatch
  performs fresh fixed MO2 and `/models` checks; both timestamps must be valid UTC,
  non-future, and at most 10 seconds old. There is no eligibility cache.
- A failed gate makes zero 4090 inference requests and attempts the 3090 once. An
  eligible request makes at most one 4090 attempt; a transport, HTTP, envelope, or
  server-model-identity failure is recorded before at most one 3090 attempt. There
  are no uncontrolled retries. In-flight inference is not terminated if MO2 starts;
  subsequent dispatches recheck the gate.
- Structured JSON evidence is uniquely named and atomically persisted on the 3090.
  It records role/model, eligibility observations and ages, attempts, endpoints,
  fallback, server model, contact booleans and counts, outcome, and no-cloud status.
- Shared storage is deliberately not used: Phase 3D payloads and evidence are small,
  and a shared path would add mutable state, races, authority ambiguity, and another
  availability/security dependency without meaningful transfer benefit. Future
  immutable large read-only artifacts may use it but can never authorize inference.
- The warning-strict suite passes 99 tests: all 86 accepted regressions and 13 Phase
  3D tests. Live Test A `1a975f47-55df-4cc5-ad8f-695c6559a78b` observed MO2
  NOT_RUNNING, fresh eligibility, and one successful real Qwen inference at the
  4090 with no fallback. Live Test B `5f98916a-700f-4c2f-a7c9-3caa288e5abb`
  observed MO2 RUNNING, made zero 4090 inference requests, and succeeded once on the
  3090. Final state independently returned to NOT_RUNNING and eligible.
- Codex's `codexsandboxoffline` execution token cannot access the private LAN. The
  unchanged acceptance module therefore ran in the normal authoritative 3090 host
  network context. This is a Codex test-harness boundary, not a GRACI runtime or
  topology change. No firewall, service, or policy was weakened.
- No cloud AI, credential, remote shell, remote process control, arbitrary network
  service, repository mutation from the 4090, or policy override was introduced.

## Phase 3C 4090 availability and MO2 policy

- `graci.availability` adds a fixed, read-only, fail-closed query for exact process
  `ModOrganizer.exe` through the 4090's narrow LAN status endpoint. Explicit states
  are RUNNING, NOT_RUNNING, UNKNOWN, and ERROR; only definitive NOT_RUNNING permits
  evaluation to continue.
- The one-time 4090 configuration is a startup Scheduled Task serving only the
  schema-version-1 MO2 response on TCP 8765. Its firewall rule allows only
  `192.168.0.100` to `192.168.0.101:8765`. It enables no WinRM, remote WMI,
  general PowerShell remoting, arbitrary query/command, termination, or service
  control. Details are under `phase3c/`.
- Eligibility precedence is node disabled, MO2 running, MO2 unknown, MO2 query
  error, endpoint unknown, endpoint unhealthy, required model unavailable, other
  policy block, then eligible. The bounded schema-valid `/models` health check is
  independent and can never override the MO2 gate.
- The warning-strict suite passes 86 tests, including all 75 prior regressions.
  Real Test A `c60baa4e-db7c-441c-b57d-877ee5e5e1e8` observed MO2 NOT_RUNNING,
  a healthy 4090 endpoint, both models, and eligibility true. Real Test B
  `ffa32f4c-7077-4075-bf62-9e8f4e95ced8` observed MO2 RUNNING while the endpoint
  remained healthy, and eligibility failed with `mo2_running`. Evidence is under
  `phase3c/evidence/`; both records prove zero inference requests.
- The 3090 remains primary and authoritative. Phase 3B Qwen/GLM routing is
  unchanged and independent of every 4090 condition. Phase 3C exposes only an
  eligibility answer; distributed execution remains unauthorized until Phase 3D.

## Phase 3B local model role routing

- `graci.routing.Phase3BRoleRouter` resolves implementer, reviewer, and verifier
  through the Phase 3A registry. Implementer resolves to Qwen on the primary 3090;
  reviewer and verifier resolve to GLM on the same localhost endpoint. Resolution
  checks enabled resources, healthy endpoint evidence, observed model presence,
  role metadata, and the Phase 3B primary-node-only policy.
- `graci.phase3b.Phase3BController` binds provider requests to each immutable
  resolution. Server-reported model identity must match exactly. The existing
  governed Qwen loop remains responsible for implementation and deterministic
  tests; GLM is invoked only after those tests pass.
- GLM has no tool or mutation interface. It receives bounded task, allowlisted
  initial/final files, ordered modification metadata, implementer action history,
  budget state, and bounded deterministic test evidence. Its strict schema permits
  only PASS or FAIL plus bounded structured findings and rationale. Malformed
  output, provider errors, or identity mismatch fail closed.
- Deterministic ordinary code adjudicates outcomes: failed tests produce FAIL;
  passing tests plus review PASS produce PASS; review FAIL produces
  REVIEW_REJECTED; unavailable or invalid required review produces REVIEW_ERROR.
  Reviewer claims never alter stored deterministic facts, so disagreement remains
  visible in separate evidence fields.
- The warning-strict suite passes 75 tests: all 65 Phase 1/2/3A regressions plus ten
  Phase 3B methods. Live run `bc5e85b9-8d5e-431c-877d-193f7f447036` observed both
  exact models at localhost, used Qwen for three governed cycles, passed two tests,
  used GLM for one valid read-only PASS review, and deterministically adjudicated
  PASS. Evidence is under `phase3b/evidence/`.
- Security review confirmed workspace containment, fixed commands, tool policy,
  Git/package/network/system prohibitions, exact endpoint/model binding, bounded
  reviewer context, read-only review, deterministic PASS authority, and the 4090
  policy block remain intact. No 4090 or cloud request was made.

## Phase 3A resource and endpoint registry

- `graci.registry` is the schema-version-1 typed, immutable authority for known
  nodes, endpoints, models, role metadata, health, and eligibility. It centralizes
  both endpoint URLs and model IDs while the existing execution configuration still
  resolves to exactly the accepted localhost 3090 and Qwen path.
- Required primary node `3090` owns `3090-llama-cpp` at
  `http://127.0.0.1:8080/v1`. Optional node `4090` owns `4090-llama-cpp` at
  `http://192.168.0.101:8080/v1` but is always policy-ineligible in Phase 3A.
- Qwen is tagged implementer/general reasoning. GLM is tagged reviewer/verifier.
  These are metadata only; autonomous routing and reviewer execution are unchanged.
- Endpoint health is unknown, healthy, or unhealthy. A bounded OpenAI-compatible
  `/models` check truthfully records HTTP, timeout/network, JSON/envelope, and model
  failures. Eligibility is separate and fails closed for disabled resources,
  missing/inconsistent references, unknown/unhealthy health, unavailable models,
  unknown roles/policy, and policy-blocked nodes.
- The warning-strict suite passes 65 tests, including all 58 Phase 1/2 regressions.
  Live validation `f2b15951-f9b7-45c9-9d5b-19cbc3a7e651` contacted only the local
  3090 `/models` endpoint, received HTTP 200, observed Qwen and GLM, made 3090/Qwen
  eligible, and confirmed 4090 `policy_blocked_node` without contacting it. Evidence
  and details are under `phase3a/`.
- Security review confirmed no workload routing, 4090 request, cloud provider,
  dependency installation, system modification, or weakening of workspace/tool
  safeguards. Health requests are bounded and unknown states fail closed.

## Phase 2C acceptance and closure

- The integrated deterministic suite covers direct and multi-file success,
  ineffective repair followed by feedback and successful repair, repair/iteration/
  model-call/inspection/modification exhaustion, malformed responses, independently
  evaluated policy violations, progress guards, provider/tool failures, false model
  success, and complete ordered evidence. The warning-strict suite passes 58 tests,
  including every Phase 1, Phase 2A, and Phase 2B regression.
- The acceptance audit repaired two in-scope defects: post-failure repair budget
  enforcement had incorrectly depended on total pre-test writes, and unexpected
  governed execution exceptions could leave the terminal reason unset. Regression
  tests cover both repairs.
- Live run `218d2969-cd66-44b2-bab0-073abecdf975` used only
  `http://127.0.0.1:8080/v1` and server-reported `qwen3.8-27b-q4_k_m`. In seven
  cycles Qwen listed scope, inspected three related files, made two governed
  replacements, and passed two deterministic tests. Evidence is under
  `phase2c/evidence/`; the fixture was automatically removed.
- Compilation, JSON validation for all six accepted evidence records, diff checks,
  safety review, evidence review, documentation review, and secret-pattern review
  passed. No 4090 or cloud workload occurred.

## Phase 2B implementation and acceptance

- The Phase 2A explicit state machine now supports governed `list_files`, multi-file
  inspection, multiple independently validated file replacements, test feedback,
  bounded repair, and retest. Every cycle separately records schema, action,
  workspace, policy, and budget validation before tool execution.
- Defaults are 12 iterations, 12 model calls, 6 inspections, 4 modifications, 2
  post-failure repairs, a 30-second command timeout, 12,000 characters per
  model-visible evidence field, 6 recent cycles, and a 2-action identical-repeat
  allowance. Evidence shows both consumption and remainder.
- Context contains only the configured file lists, test directory, budget state,
  and bounded recent completed cycles. Truncation events are explicit. Deterministic
  guards stop a third identical action, retesting a known failure without a change,
  and premature finish attempts.
- The warning-strict suite passes 50 tests. Phase 2B coverage proves multi-file
  inspection and two writes, failure feedback and repair, invalid second-action
  rejection, budget enforcement, progress guards, evidence ordering, and model
  claims unable to override deterministic tests. All Phase 1/2A tests pass.
- Live run `cf3c6de8-1bf7-404b-8ff2-c521d6d0776a` used only
  `http://127.0.0.1:8080/v1` and server-reported `qwen3.8-27b-q4_k_m`. In 7 cycles
  Qwen inspected three files, made two governed replacements, and passed both
  deterministic tests. Evidence is under `phase2b/evidence/`; the fixture was
  automatically removed.
- Security review confirmed prior containment, sensitive-path, `.git`, fixed-command,
  local provider/model, no-shell, no-Git-mutation, and no-package/network/system
  boundaries remain intact. No 4090 or cloud workload occurred.

## Phase 2A implementation and acceptance

- `graci.autonomous.AutonomousRepairController` runs one synchronous state machine
  in an existing disposable non-Git workspace. Each cycle obtains one local-model
  decision, validates its exact schema, validates policy independently, invokes a
  controlled tool, persists evidence atomically, and either continues or terminates.
- The only model actions are `inspect_file`, `write_text`, `run_tests`, and `finish`.
  Reads and writes require caller-supplied exact file allowlists; editable files must
  be a subset of readable files. Tests use the existing fixed unittest command.
- Default limits are 8 reasoning/action iterations, 2 repair writes, and a 30-second
  test timeout. Limits are host configuration, never model input. Exhaustion and all
  malformed, unsupported, policy-violating, provider, tool, and verification cases
  terminate as FAIL.
- Only a consistent governed test result with command success, exit code 0, no
  timeout, and PASS fields can establish final PASS. Model assertions and `finish`
  cannot override deterministic evidence. The last three completed cycles are fed
  back, with file and test streams truncated to 12,000 characters for model context;
  complete evidence remains in the durable record.
- The warning-strict suite passes 43 tests, including direct repair, a failed first
  repair followed by a successful second repair with test feedback, repair and
  iteration exhaustion, malformed/unsupported decisions, policy violations, tool
  and provider failures, false success resistance, deterministic evidence
  inconsistency, and multi-cycle persistence. All 32 Phase 1 tests still pass.
- Live run `2dede672-a6cf-4285-9b9f-505cb296fce6` used only
  `http://127.0.0.1:8080/v1` and server-reported model
  `qwen3.8-27b-q4_k_m`. Qwen inspected both allowlisted files, replaced only
  `calculator.py`, requested tests, and received deterministic exit code 0. The
  temporary fixture was automatically removed; durable evidence is under
  `phase2a/evidence/`.
- The first live attempt correctly failed closed before tool execution because Qwen
  emitted Markdown fences. The prompt was clarified while strict parsing remained
  unchanged; the failed preliminary record was removed as a debug artifact.
- Security regression review confirmed workspace containment, traversal/absolute
  outside-path rejection, sensitive and `.git` blocking, command allowlisting,
  absence of Git mutation, package/network/system operations, fixed endpoint/model,
  and enforced iteration/repair limits. Governed Python commands now disable bytecode
  writes and fix the hash seed to avoid stale disposable-fixture bytecode and improve
  determinism.

## Phase 1D acceptance and closure

- The deterministic integrated acceptance suite covers a valid end-to-end action,
  malformed/schema-invalid output, outside-workspace policy rejection,
  deterministic verification mismatch despite model success wording, injected
  controlled-tool failure, and durable evidence integrity for PASS and FAIL.
- The complete warning-strict suite passes 32 tests. Python compilation and Git
  whitespace/diff checks pass.
- Live run `315228d2-3413-4a8b-b059-2c3efc727ac7` used only the fixed localhost
  endpoint and `qwen3.8-27b-q4_k_m`. It validated and executed one controlled write
  in the isolated Phase 1D sandbox, then established PASS by exact read-back.
- The safety audit found and repaired one configuration defect: Phase 1 previously
  accepted any non-empty model name. Configuration now rejects every model except
  `qwen3.8-27b-q4_k_m`, with regression coverage.
- Durable closure details, live evidence, and the verified output are under
  `phase1d/`. No 4090 workload, cloud AI, external network access, dependency
  installation, secret storage, or system modification occurred.

## Phase 1C implementation

- `graci.vertical_slice.VerticalSliceController` integrates the Phase 1A local
  provider with the Phase 1B controlled tool layer for one synchronous bounded text
  file create/update in an existing explicitly configured sandbox.
- The caller fixes one allowed relative target. The model returns exactly
  `schema_version`, `action`, `target_path`, `content`, and `rationale`, and only
  `write_text` is supported. Strict schema validation and exact-target/workspace/
  sensitive-path policy validation occur before tool execution and fail closed. A
  Git repository root cannot be selected as the Phase 1C workspace, and `.git`
  paths are prohibited.
- The controlled tool writes atomically and GRACI independently reads the target.
  Exact expected/observed content equality, never a model assertion, determines
  PASS. Evidence records the task, fixed provider/model/endpoint, proposed action,
  validation, tool result, verification, final status, errors, and UTC timestamps.
- CLI callers select Phase 1C with both `--workspace` and `--target`; omitting both
  preserves the Phase 1A task interface.

## Phase 1C verification

- Warning-strict offline suite: 26 tests pass. Phase 1C coverage includes valid,
  malformed, unsupported, traversal/outside, and sensitive actions; successful
  controlled modification; verification success/failure; tool failure; truthful
  PASS/FAIL; durable evidence; and model success text unable to override failed
  deterministic verification.
- Live run `626af57f-f32a-4563-8af1-7f2a7b02b019` used only
  `http://127.0.0.1:8080/v1` and server-reported model
  `qwen3.8-27b-q4_k_m`. Schema and policy checks passed, the controlled tool wrote
  43 bytes to the isolated `phase1c/live-sandbox/result.txt`, and exact read-back
  verification passed. Durable evidence is under `phase1c/evidence/`.
- No 4090 workload, cloud AI, external network action, package installation,
  model-generated shell, Git mutation by the model, secret storage, or system
  configuration change occurred.

## Phase 1B implementation

- `graci.tools.ToolLayer` exposes deterministic programmatic interfaces for UTF-8 directory listing, text reads, atomic text creation/replacement, approved local commands, repository test execution, and read-only Git status/diff/log/HEAD observation.
- Every operation returns a structured result containing the tool and request, success, UTC start/end timestamps, error classification/message, and relevant resolved paths, process output, exit code, or timeout state.
- Workspace paths are resolved before use and must remain under the configured workspace. Traversal, absolute outside paths, symlink escapes, credential/secret path names, binary reads, and outside-workspace writes fail closed.
- Commands use executable/argument arrays with `shell=False`, a workspace-contained working directory, captured UTF-8 output, timeouts, and exit-code-based truth. The allow policy is limited to Python version checks, warning-strict unittest discovery within the workspace, and fixed read-only Git commands.
- Git observation disables system/global Git configuration, prompts, optional locks, fsmonitor, external diff, and text conversion. There are no commit, staging, checkout, reset, clean, branch mutation, push, package-manager, network, elevation, or system-configuration tools.
- The tool layer is exported beside the existing controller but is not available to a model-driven autonomous loop. That loop remains Phase 1C work.

## Phase 1B verification

- Offline suite: 18 tests pass with warnings treated as errors using `python -W error -m unittest discover -s tests -v`.
- Tests cover file create/read/replace/list, missing and binary files, traversal and absolute outside-path rejection, sensitive-path rejection, allowed/disallowed commands, timeout and stdout/stderr capture, truthful passing/failing test results, outside test-discovery rejection, and successful Git status/diff/log/HEAD reads in a temporary repository.
- Controlled local validation in a temporary repository-local sandbox created/read/replaced a file, ran `python --version`, passed a one-test unittest suite, read Git status, and rejected an attempted `../PROJECT_STATE.md` read. The sandbox was removed afterward.
- No 4090 workload, cloud AI, external network operation, dependency installation, secret storage, or system configuration change occurred.

## Phase 1A implementation

- `python -m graci "<task>"` submits one text task to the controller.
- Phase 1A configuration permits only the primary 3090 endpoint at `http://127.0.0.1:8080/v1`.
- The local llama.cpp provider uses the OpenAI-compatible chat-completions API and model `qwen3.8-27b-q4_k_m`.
- Model output must be one JSON object containing exactly `schema_version`, `status`, and `summary`. Invalid envelopes, malformed output, field/type/value errors, model identity mismatches, HTTP failures, and model-reported failures all fail closed.
- Every accepted task gets a UUID run ID and an atomically written JSON record under `runs/`, including task, UTC timestamps, provider/node/endpoint/model identity, HTTP status, validated result, final status, and errors.
- Runtime run records are intentionally ignored by Git. The accepted live evidence is versioned under `phase1a/evidence/`.
- Implementation uses only the Python standard library and stores no credentials.

## Phase 1A verification

- Offline suite: 8 tests pass with warnings treated as errors using `python -W error -m unittest discover -s tests -v`.
- Live integration run `d7e604aa-318d-47de-a735-966132894d6b` returned HTTP 200 from the localhost 3090 endpoint, reported the configured Qwen model, passed strict contract validation, and produced durable evidence.
- The Phase 1A configuration rejects the 4090 LAN endpoint and cloud endpoints. No 4090 or cloud workload was sent.
- Detailed evidence and the accepted record are under `phase1a/`.

## Current limitations

- One task is executed synchronously per CLI invocation.
- There is no cloud escalation, authentication, general service/API wrapper, or
  unbounded resource scheduling/retry path.
- Tool execution is synchronous and intentionally narrow. It has no recursive deletion,
  arbitrary shell, package management, network command, Git mutation, file patch/diff
  primitive, or streaming output. Phase 2A bounds model feedback, but durable tool
  records retain complete output.
- Phase 3B review is a single read-only post-test opinion. There is no reviewer-driven
  repair loop, reviewer tool execution, third-model adjudication, general planning,
  dynamic tool discovery, Git operations, load balancing, general scheduling,
  memory, service/API wrapper, or automatic workspace/parent creation.
- Repair uses complete-file atomic replacement, not a patch primitive. The caller
  must enumerate readable/editable files and provide the deterministic test directory.
- The 4090 requires its narrowly configured startup status task and firewall rule;
  their absence or failure makes only the 4090 ineligible.

## Qualification status

- Workspace file operations, direct command execution, Python 3.14.7, and Git 2.55.0.windows.3 passed qualification.
- The 3090 and 4090 llama.cpp model-list endpoints both returned HTTP 200 during Gate 0.
- G0.9 proved structured delegation to local Qwen through the 3090 endpoint, including programmatic JSON parsing and validation.
- Durable qualification evidence is stored under `gate0/`.

## Authoritative architecture constraints

- The 3090 PC is the primary GRACI host and must be capable of running GRACI independently.
- The 3090 local llama.cpp endpoint is `http://127.0.0.1:8080/v1`.
- The 4090 PC is optional enhanced compute capacity.
- The 4090 llama.cpp endpoint is `http://192.168.0.101:8080/v1`.
- Both llama.cpp installations currently expose:
  - `qwen3.8-27b-q4_k_m`
  - `GLM-4.7-Flash-64x2.6B-Q4_K_M`
- GRACI must never depend on the 4090 to complete required work.
- Before sending inference or other workloads to the 4090, GRACI must determine that `ModOrganizer.exe` is not running on the 4090 PC.
- If `ModOrganizer.exe` is running, GRACI must send no tasks to the 4090.
- Remote detection of exact `ModOrganizer.exe` is implemented through the narrow
  read-only Phase 3C status endpoint. Unknown and error results remain fail-closed.
- Local AI is the only implemented Phase 3 path and the 3090 is the default.
- No cloud-AI integration or routing exists in the accepted Phase 3 system.
- The repository and durable on-disk state are authoritative. Do not rely on conversation history as project state.

## Resolved Phase 3C blocker

The prior remote-process authentication blocker was resolved without broad Windows
remoting by installing the narrow Phase 3C status endpoint. It exposes no unrelated
process data or command interface.

## Next work

Phase 3 is formally complete. The next authorized phase is Phase 4 — Persistent
Memory. Phase 4 has not begun.
# Phase 4D implementation and acceptance

- Accepted starting commit `66300454a38043363eddc6c76d1d3d8d0aa04287` and a
  clean authoritative `E:\GRACI` worktree were verified before implementation.
- `graci.memory_execution` defines the strict caller-owned execution request and
  deterministic selection/serialization boundary. Requests contain explicit scope
  context, 1–50 exact keys, optional allowed types, bounded selection limit, and
  trusted `optional` or `required` mode. Models cannot derive keys, search the vault,
  choose the mode, or request arbitrary roots.
- Model-visible memory is canonical JSON classified `UNTRUSTED_CONTEXT_DATA` with
  metadata and content separated. It states that memory is not instruction or
  authority and may be stale or incorrect. Injection is independently limited to
  10 records, 2,000 content characters per record, and 12,000 aggregate serialized
  characters. Exclusion is deterministic; there is no truncation or semantic/LLM
  summarization to fit memory.
- Optional failures continue with explicit state. Required no-match, conflict,
  corrupt/truncated selection, governance/storage failure, or context-budget
  exclusion fails before model inference. Evidence records request context and keys,
  selected and supplied IDs, exclusions, conflicts, corruptions, size, mode, and
  receiving role without duplicating full content.
- The Qwen autonomous context receives the envelope. Existing task, action schema,
  file/tool allowlists, test command, loop/repair budgets, model identity, routing,
  MO2, and deterministic test authority are unchanged. Execution does not write
  memory; Phase 4B governed ingress remains the only durable boundary.
- GLM's independence policy is metadata-only memory visibility: reviewer evidence
  includes memory status and IDs, never memory content. Failed tests still suppress
  review, malformed review remains error, and deterministic Phase 3B adjudication is
  unchanged. The existing deterministic GLM integration coverage was used instead
  of a redundant live reviewer opinion.
- Synthetic 3090 Qwen acceptance used a disposable local memory root and proved
  optional no-match continuity, exact COBALT memory use and traceability, hostile
  imperative containment, required-conflict pre-inference failure, and stable
  reconstruction. Durable evidence is under `phase4d/evidence/`.
- Final warning-strict regression passed 185 tests. Compilation passed, 24 accepted
  JSON evidence files parsed, the bounded secret scan found only intentional
  rejection-test fixtures, and `git diff --check` passed.
- Canonical memory remains 3090-authoritative. No 4090 vault access, shared mutable
  memory, cloud AI, telemetry, or cloud-memory dependency was added. A future optional
  4090 inference may receive only a bounded selected envelope after existing fresh
  MO2 eligibility; this phase does not add or require that route.
- GRACI still has no semantic/vector search, embeddings, automatic conversation
  memory, automatic post-run extraction, model conflict resolution, memory authority,
  4090-owned vault, cloud memory, or Obsidian integration.
- Phase 4D stops here. The next authorized stage is Phase 4E — Persistent Memory
  Acceptance & Closure. Phase 4E has not begun.

# Phase 4E integrated acceptance and closure

- Accepted starting commit `09e99810f713f3d489f075973af79a74becc799c` and a clean
  authoritative `E:\GRACI` worktree were verified before modification.
- Phase 4A–4D compose as canonical local UTF-8 JSON storage, explicit governed
  provenance-forcing writes and exact retrieval, deterministic relevance/scope/
  lifecycle selection, and bounded Qwen context classified as untrusted data.
- Schema v1 remains readable without invented relevance or lifecycle metadata.
  Schema v2 is the governed form with exact dotted relevance keys, expiration, and
  explicit supersession. No destructive migration was performed.
- The acceptance matrix covers durability and fresh reconstruction, all four write
  provenance paths, UUIDv5 retry semantics, project/session/global isolation, exact
  relevance, supersession/history, host-clock expiration, conflicts, corruption,
  bounds, optional and required execution, hostile content, reviewer independence,
  3090/4090 authority, and cloud/privacy boundaries.
- Fresh `MemoryStore`, `MemoryPipeline`, `MemoryGovernance`, and Phase 4D preparation
  objects recovered the same synthetic AMBER record and produced the same bounded
  usable context. Required conflict stopped with zero model calls.
- A real local 3090 Qwen run received the selected/supplied AMBER memory ID, reported
  model `qwen3.8-27b-q4_k_m`, changed only the allowlisted disposable file, and passed
  deterministic tests. Memory did not alter tools, tests, budgets, routing, or policy.
- Eight hostile fixtures cover imperative, fake-system, fake-tool, routing/MO2,
  reviewer, cloud, path-looking, and shell-looking content. They remain inert envelope
  data and confer no permission.
- GLM content independence remains proven by deterministic Phase 3B/4D integration:
  reviewer input contains memory status/IDs only, failed tests remain FAIL, malformed
  output fails closed, identity is enforced, and adjudication is deterministic. A
  redundant live GLM opinion was intentionally omitted.
- Acceptance discovered and repaired one genuine defect: Phase 4D corruption evidence
  read `CorruptionDiagnostic.reason`, although the storage contract names the field
  `error`. The one-line compatibility repair plus regression test proves corrupt
  records are diagnosed and never supplied to Qwen.
- Canonical memory remains exclusively 3090-authoritative. There was no 4090 vault
  access or mutation and no shared mutable memory. Shared-drive use remains
  intentionally unnecessary; future immutable backup/export may be considered
  separately. Obsidian remains a possible derived view, never a canonical editor or
  runtime dependency.
- Phase 4 provides no semantic/vector search, embeddings, automatic conversation
  capture, unrestricted autonomous learning, model conflict resolution, comprehensive
  secret detection, Obsidian canonical editing, or cross-machine canonical-memory
  synchronization. These omissions are intentional boundaries.
- Closure evidence is `phase4e/evidence/phase4e-closure.json`; the consolidated design
  and operational contract is `phase4e/README.md`.
- **PHASE 4 — PERSISTENT MEMORY COMPLETE.** The next authorized phase is Phase 5 —
  Visualizer. Phase 5 has not begun.

# Phase 5E integrated visualizer acceptance and closure

- Accepted starting commit `27c3b5a5cef06afa55320de04c0bef591ae9ddd4` with a
  clean tree. `origin/main` remained the untouched legacy commit
  `90b94499e4edadd5843953079a72a2fa55eecbf4`; `origin/local-first` was the
  authoritative build branch.
- Phase 5A–5D compose as a frozen deterministic snapshot/event contract, bounded
  loopback GET/HEAD and SSE backend, offline responsive browser command center, and
  fail-open optional runtime observer. No visualizer component gains execution,
  tool, test, memory, routing, MO2, review, adjudication, repository, or cloud
  authority.
- Real local Qwen acceptance used `http://127.0.0.1:8080/v1`, server-reported
  `qwen3.8-27b-q4_k_m`, and `3090-primary-localhost`. It truthfully projected
  planning, governed memory preparation, reasoning, deterministic testing, and
  completion; tests passed and the terminal reason was `tests_passed`.
- Memory remains metadata-only. Tool/test facts are real and bounded. Exact GLM
  identity and distinct review/adjudication remain covered by deterministic Phase
  3B/5D integration; the unloaded reviewer was not unnecessarily loaded.
- Browser acceptance passed at 3440x1440, 2560x1440, and 1920x1080 with no
  horizontal overflow or console errors. Continuous orbital motion was visible,
  center labels remained stationary, and the reduced-motion contract disables
  animation. Backend termination produced DISCONNECTED/STALE without fabricating
  FAILED.
- Observer absence and injected observer exceptions do not alter authoritative
  results. Reconstruction needs no prior conversation, shared drive, 4090,
  Obsidian, or cloud service.
- Focused Phase 5 acceptance passes 66 tests; the complete warning-strict suite
  passes 254 tests. Python compilation, JavaScript syntax, 29 evidence JSON files,
  bounded secret/external-reference scans, static path/UI security, and
  `git diff --check` pass. No Phase 5 defect was found.
- Closure evidence is `phase5e/evidence/phase5e-closure.json`; the consolidated
  architecture and limitations are `phase5e/README.md`.
- **PHASE 5 — VISUALIZER COMPLETE.** The next authorized phase is Phase 6 — Voice.
  Phase 6 has not begun.

# Phase 6C governed runtime transcript integration

- Accepted starting commit `daa4d8496dfcfacc812fc05f3a447291191a38df` with a clean
  `main` worktree after Phase 6B closure.
- Added a thin typed adapter from Phase 6B `TranscriptionResult` to the existing
  governed runtime `run(task)` user-input boundary. Exact transcript text is passed
  unchanged and gains no additional authority.
- Failed, empty, and whitespace-only transcriptions stop before runtime submission.
  Runtime exceptions remain exceptions and governed FAIL records are returned intact;
  no response is fabricated.
- Repeated sequential inputs are supported. Each accepted transcript causes exactly
  one governed runtime call. No TTS, secondary execution, microphone logic, memory
  change, persistence/schema change, cloud path, or 4090 scheduling was added.
- The current runtime record has no appropriate input-source metadata field. Phase 6C
  therefore does not rewrite semantic text or redesign persistence to encode speech
  provenance.
- Verification and reconstruction details are recorded under `phase6c/`.

# Phase 6D local TTS and bounded audio playback

- Accepted starting commit `0e7914ebf6716bca71d30c42899d72fec0cb73ea` with a clean
  `main` worktree and 286 passing warning-strict tests.
- `AuthoritativeFinalResponse` is the sole speech-input boundary. Callers explicitly
  supply final user-facing text; Phase 6D does not inspect runtime records, prompts,
  reasoning, evidence, logs, tools, metadata, diagnostics, or exceptions.
- The unchanged authoritative text is retained in every TTS/presentation result. The
  existing Phase 6A whole-token lexicon creates a separate speech copy immediately
  before synthesis, including `GRACI` -> `GRAY-see`.
- Kokoro-82M ONNX runs in the isolated qualified Python 3.12 environment with local
  model/voice assets, CPU, and fixed `af_bella`. The one-shot worker has no network
  path and no 4090 dependency.
- Mono 16-bit WAV output is limited to 8 MiB and 120 seconds. Input is limited to
  20,000 characters; synthesis is limited to 60 seconds; playback to 125 seconds;
  synthesis and playback each permit one outstanding operation.
- Parent-owned subprocesses provide timeout termination, stop/cancel, and cleanup of
  transient text/WAV files. Failures and cleanup failures are typed and cannot alter
  an already-completed governed result.
- Focused Phase 6D tests pass 21/21 and the complete warning-strict suite passes
  307/307. A 3.563-second local Kokoro fixture synthesized successfully; its WAV was
  validated and hashed but not retained. Physical speaker playback was not performed.
- Evidence and reconstruction details are under `phase6d/`. Phase 6E has not begun.
