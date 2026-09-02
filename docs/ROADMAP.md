# GRACI roadmap

> Classification: current authorization and sequencing view
> Authority: Product Owner direction; entries do not authorize work unless explicitly marked authorized
> Verified against: Phase 8D implementation worktree based on `959347207ecbfa252ca801ca85b76d355fc4dde2`
> Last verified: 2026-09-01

| Objective | State | Meaning |
|---|---|---|
| Development-process handoff and durable memory foundation | **COMPLETE / PRODUCT OWNER ACCEPTED** | A fresh Codex session reconstructed the current product state from the repository alone; the temporary bootstrap package was then authorized for removal |
| Phase 8D — System Health & Trusted Runtime Context | **IMPLEMENTED / VERIFICATION PASS; DEPLOYMENT AND ACCEPTANCE PENDING** | Product Owner authorized the bounded objective on 2026-09-01; the current worktree implements it without deployment or service changes |
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

Cold-start acceptance remains deliberately incomplete. It must verify sustained
resident/browser readiness after the launcher exits, capture lifecycle evidence, and
receive explicit Product Owner disposition. Until then `GRACI-ISSUE-001` remains
open and Phase 8D is not a deployed or accepted capability.
