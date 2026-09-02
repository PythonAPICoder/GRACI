# GRACI repository instructions

> Classification: mandatory session entry point
> Authority: workflow guidance; canonical policy remains under `governance/`
> Verified at commit: `dbc27123e0ab25a22ac1128677d2cd385de7d662`
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
accepted. Phase 8D has not begun. System Health & Trusted Runtime Context is the
leading proposed next objective, not authorization to implement it. The open
cold-start runtime-readiness defect is tracked in
[`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md).
