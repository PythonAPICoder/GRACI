# GRACI acceptance index

> Classification: durable acceptance and validation registry
> Authority: each record is authoritative only for its stated scope
> Verified at commit: `a0a61b7298d3c85cec054cd11ca827842f2776dd`
> Last verified: 2026-09-01

Acceptance states must remain distinct:

- **Automated verified:** deterministic checks passed for named cases.
- **Live observed:** a real endpoint/component was observed at a stated time.
- **Deployed:** the named version/configuration was observed installed or running.
- **Product Owner accepted:** the Product Owner explicitly accepted the named scope.

| Record | Scope | State |
|---|---|---|
| [`ACC-0001-phase8-ui-baseline.md`](ACC-0001-phase8-ui-baseline.md) | Current Phase 8 UI/voice-presence baseline at `dbc2712` | **PRODUCT OWNER PHYSICALLY ACCEPTED** |
| [`ACC-0002-memory-foundation.md`](ACC-0002-memory-foundation.md) | Durable repository-memory/documentation foundation and fresh-session reconstruction | **PRODUCT OWNER ACCEPTED** |
| [`ACC-0003-phase8d-cold-start.md`](ACC-0003-phase8d-cold-start.md) | Phase 8D promotion, deployment, authorized router repair, and repeated controlled cold-start validation | **PRODUCT OWNER ACCEPTED** |
| [`ACC-0004-4090-llama-upgrade.md`](ACC-0004-4090-llama-upgrade.md) | Optional 4090 llama.cpp b10675 inspection, deployment, live rollback, restart, two-model, and gaming-impact validation | **PRODUCT OWNER ACCEPTED** |
| [`ACC-0005-4090-certificate-remoting.md`](ACC-0005-4090-certificate-remoting.md) | One-way certificate-authenticated WinRM from the 3090 to the 4090 | **PRODUCT OWNER ACCEPTED** |
| [`ACC-0006-4090-telemetry.md`](ACC-0006-4090-telemetry.md) | Telemetry 1.0.1 controlled startup, resources, single instance, and HUD reacquisition | **PRODUCT OWNER ACCEPTED** |
| [`ACC-0007-phase8e-stage1.md`](ACC-0007-phase8e-stage1.md) | Phase 8E Stage 1 fixture-only projection foundation and bounded Stage 2 authorization | **PRODUCT OWNER ACCEPTED** |
| [`PHASE_INDEX.md`](../history/PHASE_INDEX.md) and phase evidence | Historical phase-specific implementation and acceptance | **HISTORICAL; SCOPE VARIES BY RECORD** |

No acceptance may be widened by implication. Automated tests do not establish
physical experience; deployment does not establish reboot/resource acceptance; and
a visual baseline acceptance does not automatically prove every historical manual
race, multi-tab, autoplay, CLI microphone, or reboot scenario.
