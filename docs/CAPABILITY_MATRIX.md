# GRACI capability matrix

> Classification: current implementation/integration/deployment/acceptance map
> Authority: descriptive current state; does not grant runtime or development authority
> Verified against: promoted Phase 8D commit `a0a61b7298d3c85cec054cd11ca827842f2776dd`
> Last verified: 2026-09-01

The columns are deliberately independent. **Implemented** does not mean used by the
ordinary runtime; **tested** does not mean deployed; **deployed** does not mean
physically accepted.

| Capability | Policy/product state | Implemented and tested | Ordinary runtime integration | Deployment / acceptance |
|---|---|---|---|---|
| Strict local Qwen conversational turn | Current | Yes: `Controller`, schema-v2 validation, bounded corrective retry | Yes, typed CLI and resident/browser turn coordinator | Reputable official-release b9637 is deployed on the 3090; repeat cold-start/model readiness passed; current UI baseline is physically accepted |
| Explicit PTT, local STT, local speech | Current | Yes: bounded capture, faster-whisper CPU STT, Kokoro `af_heart`, browser-owned playback | Yes for resident/browser; CLI speech path also exists | Browser presentation is part of accepted UI baseline; some narrower QA scenarios remain separately unrecorded |
| GRACI identity and response separation | Current | Yes: GRACI system role, strict internal summary/user response split | Yes | Current subtitle and presentation accepted |
| Qwen/GLM role routing and GLM review | Current model-role policy | Yes in the Phase 3B specialized governed workflow | **No**: ordinary CLI/resident composition currently uses the plain Qwen `Controller` | Both models available on the 3090 router; ordinary-turn reviewer use not integrated |
| Governed persistent memory | Current; memory is untrusted context, never authority | Yes: local canonical JSON, governed selection, bounded execution preparation | **No** in ordinary CLI/resident composition | No shared-drive or 4090 canonical-memory dependency |
| Bounded autonomous repair loop | Future-facing self-development governance; specialized implementation exists | Yes in `AutonomousRepairController` and Phase 2/3 workflows | **No** in ordinary conversation | Does not grant self-promotion or deployment authority |
| Optional 4090 execution and failover | Current optional-compute policy | Yes: health/model checks, exact MO2 status, freshness, fail-closed eligibility | **No** in ordinary CLI/resident composition | Endpoint and policy service observed live; use remains optional and gated; bounded llama.cpp upgrade and acceptance work is authorized/in progress |
| Observer visualizer and resident turn continuity | Current | Yes: loopback backend, SSE/snapshot, latest turn, explicit controls | Yes in resident composition | Cold-start run sustained one owned resident and responsive browser/health endpoints through five minutes |
| Symmetric local/remote telemetry HUD | Presentation only | Yes: bounded schema, strict client, stale/unavailable handling | Yes in resident snapshots/UI | Telemetry agent 1.0.1 deployment confirmed; full reboot/resource/Product Owner acceptance not established |
| Current visual identity/presence | Current accepted baseline | Yes | Yes | Product Owner physically accepted at `dbc2712` |
| Trusted system health and conversational runtime context | Accepted Phase 8D capability | Yes: typed reduction, startup stages, component probes, freshness/recovery, lifecycle ledger, visualizer projection, and bounded context injection | Yes in ordinary controller composition; read-only facts cannot grant authority | Promoted/deployed; repeat automated cold-start validation passed; Product Owner accepted |
| External/cloud AI assistance | Denied by default; governed future capability | No cloud runtime path | No | Requires a current scoped Product Owner grant and future governed implementation |

See [`CURRENT_ARCHITECTURE.md`](../CURRENT_ARCHITECTURE.md) for composition and
[`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) for unresolved reliability/acceptance gaps.
