# GRACI roadmap

> Classification: current authorization and sequencing view
> Authority: Product Owner direction; entries do not authorize work unless explicitly marked authorized
> Verified against: promoted Phase 8D commit `a0a61b7298d3c85cec054cd11ca827842f2776dd`
> Last verified: 2026-09-01

| Objective | State | Meaning |
|---|---|---|
| Development-process handoff and durable memory foundation | **COMPLETE / PRODUCT OWNER ACCEPTED** | A fresh Codex session reconstructed the current product state from the repository alone; the temporary bootstrap package was then authorized for removal |
| Phase 8D — System Health & Trusted Runtime Context | **PROMOTED / DEPLOYED; COLD-START VALIDATION FAILED; ACCEPTANCE PENDING** | Commit `a0a61b7` is on `origin/main`; the resident/browser remained ready after cold start, but Code Integrity blocked the unsigned required 3090 router dependency |
| Next major objective | **NOT AUTHORIZED** | Requires a new Product Owner decision after Phase 8D handoff |
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
[`ACC-0003`](acceptance/ACC-0003-phase8d-cold-start.md). It verified sustained
resident-process, browser, endpoint, and lifecycle readiness after the resident
launcher exited. Overall validation still failed: Windows Code Integrity blocked
unsigned `llama-server-impl.dll`, the required 3090 router task returned `1`, and
runtime readiness correctly remained `unavailable`.

Phase 8D is deployed but not cold-start or Product Owner accepted. The next decision
is a security boundary choice for a trusted/signed/reputable llama.cpp artifact or
an explicitly reviewed signing/trust path. Weakening Code Integrity is not authorized
by implication. After repair, cold-start validation and explicit Product Owner
disposition remain required. `GRACI-ISSUE-001` stays open; no later objective is
authorized.
