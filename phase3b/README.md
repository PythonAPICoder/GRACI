# GRACI Phase 3B local model role routing

Phase 3B was accepted on 2026-08-27 (America/Chicago) from Phase 3A commit
`f2856a2fb762d812cda3abe6cd4a3523f7ba8454`.

## Architecture and authority

`Phase3BRoleRouter` is the sole Phase 3B role-to-resource resolver. It reads the
Phase 3A registry and requires an enabled primary node, enabled healthy endpoint,
observed enabled model, matching role metadata, and the primary-node-only Phase 3B
policy. Implementer resolves to `qwen3.8-27b-q4_k_m`; reviewer and verifier resolve
to `GLM-4.7-Flash-64x2.6B-Q4_K_M`. All three use node `3090`, endpoint ID
`3090-llama-cpp`, and `http://127.0.0.1:8080/v1`.

`Phase3BController` binds the existing governed autonomous loop to the implementer
resolution. Only consistent fixed-command test evidence can establish deterministic
success. After that success, and never as a rescue for failed tests, the controller
invokes the resolved GLM provider once. GLM receives bounded allowlisted evidence
and has no tool layer, workspace handle, mutation function, budget authority, or
resource-selection interface.

The reviewer must return exactly `schema_version`, `verdict`, `findings`, and
`rationale`. Verdict is only PASS or FAIL; findings is limited to ten exact
severity/message objects. Markdown fences, extra fields, invalid values, provider
errors, and server model-identity mismatch are errors. Deterministic adjudication is:

- tests FAIL -> FAIL, with no reviewer invocation;
- tests PASS + review PASS -> PASS;
- tests PASS + review FAIL -> REVIEW_REJECTED;
- tests PASS + review error/invalid/unavailable -> REVIEW_ERROR.

The deterministic test record and model opinion remain separate. A reviewer claim
that tests failed cannot rewrite successful deterministic evidence.

## Verification and live evidence

`python -W error -m unittest discover -s tests -v` passes 75 tests, including all
65 prior tests. Phase 3B coverage includes all three roles; unknown/missing,
unhealthy, disabled, and remote resources; exact request binding and response model
identity; PASS, FAIL, malformed, provider-error, and fact-disagreement reviews;
failed-test authority; durable findings; read-only context; and adjudication.

Live run `bc5e85b9-8d5e-431c-877d-193f7f447036` first received HTTP 200 from only
the localhost `/models` endpoint and observed both exact model IDs. In a disposable
non-Git fixture, Qwen inspected and repaired `discount.py`, then two deterministic
tests passed. GLM received 2,464 characters of bounded review evidence, returned a
valid strict PASS with its exact server-reported identity, and deterministic
adjudication returned PASS. The fixture was automatically removed. The complete
record is `evidence/bc5e85b9-8d5e-431c-877d-193f7f447036.json`; reproduce with
`python -m phase3b.run_live_acceptance`.

## Security and limitations

The complete review found no weakening of workspace containment, sensitive-path
blocking, fixed `shell=False` test execution, arbitrary-shell prohibition, Git
mutation prohibition, package/network/system restrictions, model identity checks,
or deterministic PASS authority. Reviewer input is restricted to caller-allowlisted
task files and bounded run facts. Phase 3B contains no 4090 selection, fallback, or
retry: even a healthy fake remote endpoint is policy-blocked. The live runner made
no 4090 or cloud request.

There is no reviewer repair loop, reviewer tool use, third model, load balancing,
remote failover, ModOrganizer detection, cloud escalation, semantic memory,
visualizer, voice, autonomous Git mutation, or package installation. Phase 3C —
4090 Availability & MO2 Policy is next and has not begun.
