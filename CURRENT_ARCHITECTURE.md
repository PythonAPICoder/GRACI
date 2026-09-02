# Current GRACI architecture

> Classification: current descriptive architecture
> Authority: implementation description; canonical policy remains under `governance/`
> Verified against: promoted Phase 8D commit `a0a61b7298d3c85cec054cd11ca827842f2776dd`
> Last verified: 2026-09-01

Accepted policy is canonical in
[`governance/CURRENT_POLICY.md`](governance/CURRENT_POLICY.md). This document
describes the composition currently present in the repository; it grants no new
authority.

## Ordinary operator composition

The normal typed CLI and resident/browser path is:

`explicit typed input or PTT release -> ExplicitTurnCoordinator -> Controller -> fixed local 3090 Qwen -> strict result validation -> AuthoritativeFinalResponse -> typed response and optional local speech`

`graci.operator_cli.build_operator_composition` constructs a plain `Controller`
using the fixed `Config`: local endpoint `http://127.0.0.1:8080/v1`, Qwen model
`qwen3.8-27b-q4_k_m`, and local 3090 identity. The model reasons on behalf of GRACI;
it is not the product identity.

The composition also owns a Phase 8D `RuntimeHealthService`. Immediately before a
governed model request, the controller takes one bounded trusted-context snapshot.
The provider appends those typed, timestamped facts to the system message while
preserving the user's task unchanged. The context explicitly cannot grant authority,
override governance, authorize actions, or replace the task. It is stored with the
run record as evidence; provider-context failure degrades to no context and does not
silently create authority.

Strict result schema v2 separates internal `summary` from `user_response`. Only a
validated nonblank PASS `user_response` can become the immutable
`AuthoritativeFinalResponse`. Malformed/raw/fenced/schema-invalid output is rejected.
One corrective model generation is allowed only after model-content validation
rejection within the same governed run.

Each accepted task receives a UUID and an atomically written JSON run record under
`runs/`. Run records are evidence, not reusable authority or product memory.

## Interaction and presentation

Typed input and successful local STT transcripts share the same governed turn
coordinator. Browser and CLI voice remain explicit PTT; release authorizes the spoken
submission. There is no wake word, VAD authority, always listening, or autonomous
follow-up.

The resident composes:

- Windows PCM capture and local faster-whisper `small.en` CPU `int8` STT;
- local Kokoro CPU synthesis fixed to `af_heart` at speed `1.00`;
- speech-only normalization and `GRACI -> GRAY-see` pronunciation;
- one in-memory, expiring, single-claim browser playback artifact;
- a `VoiceLifecycle` that publishes trusted LISTENING/SPEAKING only at accepted
  capture/playback boundaries; and
- a loopback visualizer, latest-turn projection, SSE stream, browser PTT operator,
  and bounded Restart callback.

The resident additionally samples system health at a bounded interval. The fixed
read-only collector observes the exact startup tasks, task launcher results, owned
resident process, actual resident health endpoint, 3090 router and model inventory,
Qwen/GLM load state, optional 4090 endpoint/MO2/eligibility, local STT/TTS assets,
and the timezone-aware OS clock. Required component facts reduce to
`ready/degraded/unavailable/recovering`; stale observations degrade rather than being
presented as current. Optional 4090 failure remains visible without making it a 3090
baseline dependency.

The visualizer serves only three packaged static resources and fixed API routes. Its
POST allowlist is PTT begin/chunk/finish/cancel, Restart, speech claim, and speech
lifecycle. Speech audio is fetched through an opaque artifact ID plus independent
claim token. No browser route accepts an arbitrary task, path, URL, command, model
override, memory request, or authority-bearing response.

The Product Owner-accepted UI baseline at `dbc2712` uses a symmetric 3090/presence/
4090 HUD, Data Chatter during trusted processing observations, and a continuous
voice-reactive outer ring during browser-owned playback. See
[`ACC-0001`](docs/acceptance/ACC-0001-phase8-ui-baseline.md).

## Resident and startup ownership

`graci.resident_host` owns one browser-operator composition, a GRACI-specific
exclusive lock, and the loopback visualizer. A validated cooperative stop request
ends it. A one-shot CLI refuses to run while the resident is active.

The 3090 model router and resident use separate limited current-user at-logon tasks:
`\GRACI 3090 llama.cpp Router` and `\GRACI Resident Host`. Their scripts and
validated state live under [`ops/`](ops/). The router is configured for the two
approved local models and bounded model lifecycle management.

The resident task owns the startup launcher, not the continuing child lifetime. A
successful task result means the launcher observed a matching resident during its
bounded startup wait and exited successfully; it does not establish that the resident
remained alive or that the visualizer/browser path remained ready. The current status
script now distinguishes task absence from task-enumeration access denial, task
registration, launcher success, owned-process liveness, and actual loopback runtime
response. These observations remain facts, not alternate runtime authority.

The resident writes a bounded JSONL lifecycle ledger at
`.runtime/resident-host/lifecycle.jsonl`. It records starting, publication,
readiness transitions, periodic heartbeats, clean stops, bounded exception evidence,
and detection that a prior lifecycle ended without a terminal event. This improves
later diagnosis but cannot guarantee a root cause after abrupt OS or hardware loss.

## Specialized capabilities not in every ordinary turn

The repository also implements:

- `AutonomousRepairController`: bounded allowlisted file/tool/test repair loops;
- `Phase3BController`: Qwen implementation followed by independent GLM evidence
  review and adjudication;
- `Phase3DDistributedRouter`: optional 4090 routing/failover with health, freshness,
  model identity, and exact MO2 gating; and
- Phase 4 governed persistent memory: canonical local JSON, writes, selection,
  supersession, conflict handling, and bounded untrusted execution context.

These capabilities are tested and historically accepted within their specialized
flows. The ordinary CLI/resident composition does not currently instantiate the
Phase 3B workflow, memory governance, autonomous repair loop, or distributed router.
Future composition should select capabilities according to task, policy, latency,
resources, and verification needs rather than call every subsystem unconditionally.

## Compute and telemetry

The 3090 is authoritative and sufficient. Qwen is the primary implementer/general
reasoning model; GLM is the reviewer/verifier in the specialized reviewed workflow.

The optional 4090 has two separate read-only observations:

- exact `ModOrganizer.exe` state at
  `http://192.168.0.101:8765/graci/v1/mo2`, which participates in fail-closed
  workload eligibility; and
- telemetry agent `/health` and `/telemetry` at
  `http://192.168.0.101:8767`, which is presentation-only and cannot authorize
  routing or compute.

Telemetry schema 2 supplies bounded GPU/CPU/RAM facts, explicit unobserved CPU
temperature, agent version/priority state, and timestamps. The resident's strict
client treats timeout, staleness, malformed data, schema/identity mismatch, and
unreachability as unavailable. Local 3090 telemetry is separately collected for the
HUD.

The 3090 also has one-way certificate-authenticated WinRM over HTTPS to the 4090,
mapped to dedicated identity `VR-Gamer\GRACI_Remote` and firewalled to the 3090.
The non-exportable client key lives in the 3090 current-user certificate store;
routine sessions require no password. The password route is break-glass recovery
only. This is an operator/deployment mechanism, not an ordinary model tool or source
of runtime authority. Optional workload and mutation still require current task
authority and exact MO2 gating; the 3090 remains independently sufficient.

## Storage and authority boundaries

The repository, run records, and governed memory remain canonical on the 3090.
Shared storage is optional infrastructure and never authoritative GRACI storage.
Memory is untrusted context, not permission. The 4090, shared drive, Obsidian, and
cloud are not canonical-memory dependencies.

No cloud AI runtime path exists. External assistance requires an active scoped grant
and future governed implementation. Free-form Markdown is human documentation and
must never be parsed to grant runtime capability.

## Remaining architectural and acceptance gap

Phase 8D is promoted and deployed. The prior startup-status false-negative is
repaired. The first controlled cold start proved sustained resident-process and
browser readiness after the launcher exited but exposed a Code Integrity block in
3090 llama.cpp b10516. The Product Owner-authorized repair preserved the enforced
policy, installed official-release b9637 at the pinned production path, and retained
the blocked build as a recoverable backup. A repeat full cold start then sustained
both launcher success, one resident instance, browser/health response, primary
router/model readiness, and lifecycle heartbeats through five minutes.

The Product Owner accepted Phase 8D after that passing repeat. The separate optional
4090 upgrade has since deployed official b10675, passed real Qwen and GLM inference,
passed an exercised rollback/re-promotion cycle, and passed a controlled restart
without changing its task, models, firewall, or MO2 gate. The Product Owner accepted
the upgrade and verified gaming impact. See
[`ACC-0004`](docs/acceptance/ACC-0004-4090-llama-upgrade.md).
