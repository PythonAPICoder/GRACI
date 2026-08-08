# G.R.A.C.I. Governance Index

## Purpose

This directory contains the governing requirements for the design, implementation, testing, operation, and evolution of G.R.A.C.I. (General Reasoning, Automation, Coordination, and Intelligence).

## Precedence

Read governance documents in this order:

1. `MASTER_SYSTEM_SPEC.md`
2. `ADDENDUM_001_CONTINUOUS_VERIFICATION.md`
3. `ADDENDUM_002_MULTI_NODE_AI.md`
4. `ADDENDUM_003_RELIABILITY_RECOVERY.md`
5. `ADDENDUM_004_CAPABILITY_GOVERNANCE.md`
6. Future numbered addendums in ascending numerical order

The master specification is the immutable baseline.

If a later addendum explicitly conflicts with an earlier requirement, the newest applicable addendum governs.

## Change Policy

Do not rewrite the master specification to incorporate later changes.

Changes must be made through a new numbered addendum.

Use the next unused number.

Each addendum should state:

- what it changes or extends;
- why the change exists;
- which earlier requirement it supersedes, if any.

## Configuration vs. Governance

Governance describes durable behavior and architecture.

Do not place transient deployment details in governance unless they are requirements.

Examples that belong in runtime or environment configuration:

- IP addresses;
- current hostnames;
- ports;
- credentials;
- currently installed model names;
- temporary paths;
- machine-specific endpoint values.

## Supporting Logs

Engineering history is stored under `../logs/`.

The initial templates are:

- `DEVELOPMENT_LOG.md`
- `TEST_LOG.md`
- `FAILURE_LOG.md`
- `DECISION_LOG.md`

These files may evolve as the application develops.
