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
6. `ADDENDUM_005_ARCHITECTURE_2_FOUNDATION.md`
7. `ADDENDUM_006_ARCHITECTURE_2_PHASE_1A.md`
8. `ADDENDUM_007_ARCHITECTURE_2_PHASE_1B.md`
9. `ADDENDUM_008_ARCHITECTURE_2_PHASE_1C.md`
10. `ADDENDUM_009_ARCHITECTURE_2_PHASE_1D.md`
11. `ADDENDUM_010_ARCHITECTURE_2_PHASE_1E.md`
12. `ADDENDUM_011_ARCHITECTURE_2_PHASE_1F.md`
13. `ADDENDUM_012_ARCHITECTURE_2_PHASE_1G.md`
14. `ADDENDUM_013_ARCHITECTURE_2_PHASE_1H.md`
15. `ADDENDUM_014_ARCHITECTURE_2_PHASE_1I.md`
16. `ADDENDUM_015_ARCHITECTURE_2_PHASE_1J.md`
17. `ADDENDUM_016_ARCHITECTURE_2_PHASE_1K.md`
18. `ADDENDUM_017_ARCHITECTURE_2_PHASE_1L.md`
19. `ADDENDUM_018_ARCHITECTURE_2_PHASE_1M.md`
20. `ADDENDUM_019_ARCHITECTURE_2_PHASE_1N.md`
21. Future numbered addendums in ascending numerical order

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
