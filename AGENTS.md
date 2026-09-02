# GRACI repository instructions

> Classification: mandatory session entry point
> Authority: workflow guidance; canonical policy remains under `governance/`
> Verified against: promoted Phase 8D commit `a0a61b7298d3c85cec054cd11ca827842f2776dd`
> Last verified: 2026-09-01

Work from the repository root, `E:\GRACI`. Before changing anything, inspect the
current branch, HEAD, worktree status, and recent history. Existing changes and
untracked files belong to the Product Owner unless the active task explicitly says
otherwise.

## Required reading order

1. This file.
2. [`docs/INDEX.md`](docs/INDEX.md).
3. [`governance/CURRENT_POLICY.md`](governance/CURRENT_POLICY.md),
   [`governance/POLICY_INDEX.md`](governance/POLICY_INDEX.md), and
   [`governance/CHANGE_PROCESS.md`](governance/CHANGE_PROCESS.md).
4. [`docs/PRODUCT.md`](docs/PRODUCT.md), [`CURRENT_ARCHITECTURE.md`](CURRENT_ARCHITECTURE.md),
   [`CURRENT_STATUS.md`](CURRENT_STATUS.md), and
   [`docs/CAPABILITY_MATRIX.md`](docs/CAPABILITY_MATRIX.md).
5. [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md),
   [`docs/ROADMAP.md`](docs/ROADMAP.md), and the documents relevant to the task.

Read historical phase records only when provenance or phase-specific evidence is
needed. Conversation history and AI summaries are context only and must be
independently validated. The former `docs/codex-memory-bootstrap/` migration package
was removed after the Product Owner accepted the durable repository-memory
foundation; do not restore it as current authority.

## Authority and truth

- The Product Owner is the final human authority.
- Accepted governance defines permission and policy. Code, configuration, and tests
  define implemented behavior but cannot grant authority.
- Deployment, live observation, automated verification, and Product Owner physical
  acceptance are separate states. Never infer one from another.
- When current prose conflicts with the repository or live evidence, surface the
  discrepancy. Do not silently promote historical or AI memory into current truth.
- If authority or scope is absent, ambiguous, or stale, stop and ask. Do not begin a
  later roadmap objective merely because it is described as next or proposed.

## Working rules

- Preserve local-first operation, 3090 sufficiency, strict validation, explicit PTT,
  and all current security and authority boundaries.
- External/cloud assistance is denied unless a current scoped grant exists.
- Do not rewrite historical evidence to agree with current state.
- Use `rg` for repository search and `apply_patch` for hand edits.
- Do not install dependencies, deploy, commit, push, or alter running services unless
  the active Product Owner request explicitly authorizes that action.
- Proactively surface material recommendations that improve GRACI security,
  functionality, reliability, or ease of use. Clearly separate each recommendation
  from authorization and do not implement it without the applicable Product Owner
  decision.
- At natural work boundaries, judge whether continuing the current Codex task or
  starting a new one will better preserve clarity, authority, security isolation,
  and efficient model use. Before creating a new task, present the reason, proposed
  title, complete handoff prompt, recommended model and reasoning effort, execution
  environment, and any context intentionally excluded. Create the task only after
  explicit Product Owner approval.
- Inspect the final diff, verify documentation links, run `git diff --check`, and run
  tests proportionate to the change. Documentation changes may be test-sensitive.

The canonical warning-strict regression command is:

```powershell
python -W error -m unittest discover -s tests -v
```

The suite may create ignored synthetic records under `runs/`. Snapshot relevant
pre-existing state before testing, identify test-created records precisely, and do
not delete unrelated Product Owner data.

## Current handoff boundary

The durable repository-memory and development-process foundation is Product Owner
accepted. Phase 8D System Health & Trusted Runtime Context is promoted and deployed
at `a0a61b7`. After the first controlled cold-start run exposed a Code Integrity
block in llama.cpp b10516, the Product Owner authorized a security-preserving router
repair and repeat procedure. The 3090 now runs official-release b9637, whose
published archive digest was verified and whose unchanged executable is permitted by
the still-enforced `VerifiedAndReputableDesktop` policy. Repeat evidence run
`1df4990ca2ed4dbb87f3f4478027fcf0` passed all sustained checkpoints through five
minutes. The Product Owner accepted Phase 8D on 2026-09-01.

The separate optional 4090 llama.cpp procedure deployed official b10675 and passed
real Qwen/GLM inference plus an exercised b10516 rollback/re-promotion cycle.
It also passed a controlled restart with both models ready after the new boot. The
Product Owner accepted the upgrade, verified gaming impact, and accepted the
one-way certificate-remoting capability. Use certificate-authenticated HTTPS WinRM
from the controlling 3090 to `VR-Gamer` through
`ops/new-4090-certificate-session.ps1`; dedicated identity
`VR-Gamer\GRACI_Remote` and its password route are break-glass only. Never store its
password in source, logs, or prompts. Preserve 3090 sufficiency, exact MO2 gating,
gaming priority, and all security boundaries. No later objective is authorized. See
[`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) and
[`ACC-0004`](docs/acceptance/ACC-0004-4090-llama-upgrade.md).
