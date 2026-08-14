# G.R.A.C.I.

**G.R.A.C.I.** = **General Reasoning, Automation, Coordination, and Intelligence**

This package contains the initial engineering governance foundation for the G.R.A.C.I. autonomous personal AI assistant.

## Intended Location

Unzip the package so the repository/root folder is:

`E:\GRACI`

The governance files do not hard-code machine IP addresses, model assignments, or other transient deployment facts. Those should be discovered or configured during implementation.

## Start Here

Implementation agents should begin with:

`AGENTS.md`

`AGENTS.md` directs agents to the immutable master specification and all numbered addendums.

For a current, plain-language and technical snapshot, read:

- `CURRENT_STATUS.md` — implemented capabilities, limitations, verification status, and recommended next phase
- `CURRENT_ARCHITECTURE.md` — the architecture that exists today and its deferred boundaries

These are living documents. They summarize the repository but do not supersede governance.

## Governance Structure

- `docs/governance/MASTER_SYSTEM_SPEC.md` — immutable baseline
- `docs/governance/ADDENDUM_001_CONTINUOUS_VERIFICATION.md` — continuous testing, logging, live runtime verification
- `docs/governance/ADDENDUM_002_MULTI_NODE_AI.md` — multi-node Ollama/local AI architecture
- `docs/governance/ADDENDUM_003_RELIABILITY_RECOVERY.md` — rollback, self-update, recovery, backups, self-diagnostics
- `docs/governance/ADDENDUM_004_CAPABILITY_GOVERNANCE.md` — capability registry, model qualification, privacy, resource scheduling, reproducibility
- `docs/governance/GOVERNANCE_INDEX.md` — precedence and amendment policy

## Engineering Logs

Initial log templates are under:

`docs/logs/`

The implementation system should keep these useful and concise rather than dumping every command or token into them.

## Baseline Rule

Do not rewrite `MASTER_SYSTEM_SPEC.md` when requirements change.

Create a new numbered addendum.
