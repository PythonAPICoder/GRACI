# GRACI development process

> Classification: current Lead Architect/Developer workflow
> Authority: Product Owner-approved working model; governance controls authority and promotion
> Verified at commit: `dbc27123e0ab25a22ac1128677d2cd385de7d662`
> Last verified: 2026-09-01

## Lifecycle

`REQUEST -> VERIFY CURRENT STATE -> DEFINE SCOPE/AUTHORITY -> DESIGN -> PRODUCT OWNER APPROVAL WHEN REQUIRED -> IMPLEMENT -> FOCUSED TEST -> REGRESSION -> REVIEW -> REPAIR -> ACCEPTANCE -> PRODUCT OWNER PROMOTION/DEPLOYMENT DECISION`

Codex may act as GRACI's Lead Architect and Developer within the Product Owner's
current scope. That role does not authorize speculative follow-up, policy changes,
deployment, merge, commit, push, external assistance, or a later roadmap objective.

## Before implementation

1. Follow [`AGENTS.md`](../AGENTS.md) and reconstruct current context through
   [`docs/INDEX.md`](INDEX.md).
2. Inspect Git status, HEAD, recent history, relevant code/configuration/tests, and
   live state when deployment claims matter.
3. Separate policy, desired product behavior, implemented capability, ordinary
   integration, deployment, and acceptance.
4. State scope, exclusions, risks, acceptance criteria, and any Product Owner choice
   needed before making materially different changes.

## During implementation

- Preserve existing user changes and unrelated untracked files.
- Keep changes bounded to the authorized objective.
- Update the canonical home of any changed fact; link rather than duplicate.
- Do not rewrite historical phase evidence.
- Keep implementation, independent review, deterministic verification, and Product
  Owner acceptance distinguishable.
- Local Qwen/GLM capabilities and future authorized external help remain subordinate
  to governance, typed controls, tests, and Product Owner authority.

## Architect recommendation duty

During GRACI development, the Lead Architect and Developer should proactively surface
material recommendations that improve security, functionality, reliability, or ease
of use. A recommendation should state the user benefit, security or privacy effect,
scope, dependencies, likely cost or complexity, important risks, acceptance criteria,
and suggested roadmap timing when those details help the Product Owner decide.

Recommendations are advisory. They do not authorize implementation, installation,
policy change, deployment, commit, push, external access, or expansion of the active
task. Keep them relevant and prioritized so useful development work is not buried in
speculative feature lists.

## Codex task boundaries, handoffs, and model choice

The Lead Architect and Developer must evaluate natural work boundaries and recommend
whether to continue the current Codex task or begin a new one. A new task is normally
appropriate when the objective or roadmap phase changes materially, accumulated
history is no longer useful, a clean authority or security boundary is needed, work
should be isolated in a separate worktree, or a different model and reasoning effort
would materially improve cost or quality. Continue the current task when the objective
and authority are unchanged and its live context remains important.

Before creating a new task, present the Product Owner with:

1. the reason for the proposed boundary;
2. the proposed task title;
3. a complete handoff prompt;
4. the recommended model and reasoning effort, with a brief cost and quality reason;
5. the proposed execution environment, including current checkout or isolated
   worktree; and
6. any context that will be intentionally excluded or may not carry forward.

Wait for explicit Product Owner approval before creating the task. A handoff must
state the authorized objective, authority limits, repository and worktree state,
completed work, relevant Product Owner changes, controlling documents, important
decisions, open risks or blockers, verification evidence, success criteria, and the
exact next action. It must not copy credentials or other secrets. Creating a task
does not authorize its objective, broaden its scope, or permit commit, deployment,
external access, or another controlled action.

Choose the least costly model and reasoning effort that is likely to complete the
work reliably. Use Luna at low effort for bounded routine work, Terra at medium
effort as the normal development baseline, Terra at high effort for complicated
implementation or review, and Sol at high or xhigh effort for architecture,
governance, security, difficult failures, or major integrations. Reserve max or
ultra effort for exceptional quality-critical work with a clear reason. Adjust the
recommendation when current model availability, task evidence, or measured results
show a better fit. This rule governs Codex development tasks and does not change
GRACI's runtime model policy.

## Verification and handoff

Use focused tests first. The complete warning-strict regression is:

```powershell
python -W error -m unittest discover -s tests -v
```

The complete suite includes one-shot CLI tests whose safety contract rejects use
while the GRACI resident owns its runtime lock. Run the complete suite only when the
resident is already inactive or the current scope explicitly authorizes a bounded
stop, test, restart, and readiness check. Do not stop a running resident merely to
satisfy the regression command. When the resident remains active, record the
environmental block and run the relevant focused suites.

Also inspect the complete diff, validate tracked JSON and relevant documentation
links, run `git diff --check`, confirm no out-of-scope files changed, and report
runtime/deployment actions explicitly. Tests may create ignored synthetic `runs/`
records; remove only records proven to have been generated by the current test run.

The handoff must report files changed, behavior changed, verification performed,
open risks, deployment/acceptance state, Git status, and the exact next decision. A
successful implementation or test run never authorizes deployment or promotion.
