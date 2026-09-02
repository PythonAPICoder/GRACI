# GRACI roadmap

> Classification: current authorization and sequencing view
> Authority: Product Owner direction; entries do not authorize work unless explicitly marked authorized
> Verified against: promoted Phase 8D commit `a0a61b7298d3c85cec054cd11ca827842f2776dd`
> Last verified: 2026-09-01

| Objective | State | Meaning |
|---|---|---|
| Development-process handoff and durable memory foundation | **COMPLETE / PRODUCT OWNER ACCEPTED** | A fresh Codex session reconstructed the current product state from the repository alone; the temporary bootstrap package was then authorized for removal |
| Phase 8D — System Health & Trusted Runtime Context | **COMPLETE / PROMOTED / DEPLOYED / PRODUCT OWNER ACCEPTED** | Commit `a0a61b7` is on `origin/main`; an authorized reputable-build repair preserved Code Integrity, repeat run `1df4990ca2ed4dbb87f3f4478027fcf0` passed through five minutes, and the Product Owner accepted the phase |
| Optional 4090 llama.cpp upgrade | **COMPLETE / PRODUCT OWNER ACCEPTED** | Official b10675 is deployed; both models passed after a new boot, b10516 rollback was exercised, gaming impact is verified, and 3090 sufficiency plus MO2 priority remain intact |
| One-way 3090-to-4090 certificate remoting | **COMPLETE / PRODUCT OWNER ACCEPTED** | Passwordless HTTPS WinRM maps only the 3090 client certificate to `GRACI_Remote`; password access is break-glass only |
| Objective after 4090 upgrade | **NOT AUTHORIZED** | Requires a new Product Owner decision after the authorized 4090 handoff |
| Ordinary runtime capability selection | **PRODUCT DIRECTION** | Eventually choose routing, review, memory, optional compute, recovery, and verification according to task/policy/latency/resources rather than invoking all subsystems on every turn |
| Wake word, VAD authority, always listening, autonomous follow-up | **DEFERRED / UNAUTHORIZED** | Requires separate Product Owner decision and governed implementation |
| External/cloud runtime assistance | **FUTURE GOVERNED CAPABILITY** | Denied by default; no runtime path exists |

## Phase 8D implementation and remaining gate

Phase 8D now implements typed, timestamped runtime-readiness observations; trusted
local date/time/timezone; 3090/router/Qwen/GLM availability and load state; optional
4090 reachability, MO2, eligibility, and endpoint/model health; STT/TTS resource
readiness; freshness and recovery transitions; bounded trusted conversational system
context; loopback/UI projection; and bounded resident lifecycle evidence.

The startup/readiness contract distinguishes:

- missing;
- access denied / unknown;
- registered;
- launcher succeeded;
- process alive; and
- runtime ready.

Runtime readiness comes from owned-process and actual endpoint behavior, not task
registration or exit code. The implementation adds no repair, routing, microphone,
cloud, or autonomous execution authority.

The controlled cold-start procedure is recorded in
[`ACC-0003`](acceptance/ACC-0003-phase8d-cold-start.md). The first run preserved the
resident/browser success but failed overall when Windows Code Integrity blocked
unsigned b10516 router code. The Product Owner then authorized a security-preserving
repair. Official-release b9637 matched its published SHA-256 digest, passed the
unchanged active reputation policy, supported every pinned GRACI flag, and completed
an isolated CUDA-build router/model request using the pinned `--n-gpu-layers all`
setting before deployment. No Code Integrity, Smart App Control, signing, trust, or
allowlist setting was changed.

Repeat run `1df4990ca2ed4dbb87f3f4478027fcf0` followed a full shutdown and new boot.
Both launchers returned `0`; one resident instance, browser/health endpoint, primary
router/model inventory, and lifecycle heartbeats remained valid at the sustained 60,
120, and 300 second checkpoints. The automated summary is `PASS`.

Phase 8D is deployed, automated cold-start validated, and Product Owner accepted.
`GRACI-ISSUE-001` is closed. The separately bounded 4090 llama.cpp procedure is
deployed and live validated as recorded in [`ACC-0004`](acceptance/ACC-0004-4090-llama-upgrade.md).
The 4090 upgrade and one-way certificate remoting are Product Owner accepted. No
objective after them is authorized.
