# GRACI repository instructions

> Classification: mandatory session entry point
> Authority: workflow guidance; canonical policy remains under `governance/`
> Verified through: Phase 8E Stage 3 Product Owner acceptance and routine-launch promotion on 2026-09-02
> Last verified: 2026-09-02

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
gaming priority, and all security boundaries. At that acceptance boundary, no later
objective was authorized. See
[`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) and
[`ACC-0004`](docs/acceptance/ACC-0004-4090-llama-upgrade.md).

The Product Owner subsequently accepted the Phase 8E read-only Obsidian review
design and the Stage 1 fixture-only implementation. Stage 1 may be committed and
pushed to `main`. The Product Owner also authorized Stage 2 local Windows inspection,
exact control selection, boundary implementation, rollback, and synthetic
verification. Stage 2 does not authorize Obsidian installation or configuration,
real-memory access, real-data generation, network or firewall changes, deployment,
automatic refresh, resident changes, or Stage 3 and later work. See
[`ACC-0007`](docs/acceptance/ACC-0007-phase8e-stage1.md).

Stage 2 synthetic Windows boundary verification, rollback, and reapply subsequently
passed. The Product Owner accepted the lack of BitLocker as an intentional
physical-security risk and directed that BitLocker must not be installed, enabled,
configured, or deployed on any drive, folder, or file on either system. This does
not authorize real data or Stage 3 or Stage 4 work. The Product Owner subsequently
accepted Stage 2 and authorized its commit and push to `main`. The Product Owner
reports that Obsidian is already installed but unused. At the Stage 2 boundary it
had not been inspected, configured, or qualified, and Stage 3 remained unauthorized.
That restriction was later superseded only by PO-DEC-031 and PO-DEC-032. See
[`ACC-0008`](docs/acceptance/ACC-0008-phase8e-stage2-windows.md), `PO-DEC-029`, and
`PO-DEC-030`.

The Product Owner then authorized a narrow Stage 3 test of the exact existing
per-user Obsidian executable using synthetic data, exact review-SID read-and-execute
access, and a review-SID-only outbound firewall block. The review token read the
program and projection, and projection writes remained denied, but Obsidian did not
remain running or register the synthetic vault. The test failed closed and rollback
restored the original Obsidian permissions, firewall state, and review profile.
No application was qualified by that attempt. See
[`PHASE_8E_STAGE3_OBSIDIAN_TEST_PLAN.md`](docs/PHASE_8E_STAGE3_OBSIDIAN_TEST_PLAN.md)
and `PO-DEC-031`.

The Product Owner then authorized a separate local Obsidian copy for `GRACI_Review`
while preserving the Product Owner account's read access. The exact verified copy
is installed under the review profile and passed the real-token synthetic test: 25
notes readable, immutable generation write denied, vault registered, protected files
unchanged, and viewer-only outbound update attempts blocked. The Product Owner's
existing Obsidian installation and settings remained unchanged; Stage 2 verification
and resident HTTP health passed. The Product Owner accepted Stage 3 and authorized
routine launch, commit, and push. The exact launcher was promoted and passed under
the real review token with zero observed non-loopback connections. This acceptance
does not authorize real data, automatic refresh, runtime integration, Stage 4, or
any BitLocker change. See [`ACC-0009`](docs/acceptance/ACC-0009-phase8e-stage3-obsidian.md),
`PO-DEC-033`, and the Stage 3 evidence.
