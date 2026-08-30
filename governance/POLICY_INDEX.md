# G.R.A.C.I. Policy Index

This is the stable index for accepted current G1 policy.
`CURRENT / IMPLEMENTED BEHAVIOR` means accepted current policy describing behavior
already implemented.
`CURRENT / FUTURE CAPABILITY` means accepted current governance that applies
prospectively to a capability that is not implemented. Neither status grants runtime
authority. Links to phase records are historical evidence, not mutable current
policy.

| ID | Title | Status | Canonical policy | Implementation | Deterministic test | Historical evidence |
|---|---|---|---|---|---|---|
| AUTH-001 | Product Owner authority and active authorization | CURRENT / IMPLEMENTED BEHAVIOR | [Identity and human authority](CURRENT_POLICY.md#identity-and-human-authority) | — | [Governance checks](../tests/test_governance.py) | [QA-001 state](../PROJECT_STATE.md#qa-001-graci-identity-and-conversational-response-contract-repair) |
| AUTH-002 | Markdown cannot grant runtime authority | CURRENT / IMPLEMENTED BEHAVIOR | [Human and machine consumption boundary](CURRENT_POLICY.md#human-and-machine-consumption-boundary) | — | [Governance checks](../tests/test_governance.py) | — |
| AUTONOMY-001 | Bounded authorized local work | CURRENT / IMPLEMENTED BEHAVIOR | [Autonomy and interaction boundaries](CURRENT_POLICY.md#autonomy-and-interaction-boundaries) | [`ExplicitTurnCoordinator`](../graci/turn_coordinator.py) | [Phase 7A tests](../tests/test_phase7a_turn_coordinator.py) | [Phase 7A](../phase7a/README.md) |
| EXTERNAL-001 | External assistance denied by default | CURRENT / FUTURE CAPABILITY | [External assistance and cloud permission](CURRENT_POLICY.md#external-assistance-and-cloud-permission) | No external runtime capability | [Governance checks](../tests/test_governance.py) | — |
| EXTERNAL-002 | Task and project grant scopes | CURRENT / FUTURE CAPABILITY | [External assistance and cloud permission](CURRENT_POLICY.md#external-assistance-and-cloud-permission) | No external runtime capability | [Governance checks](../tests/test_governance.py) | — |
| LOCAL-001 | Local-first and 3090-sufficient operation | CURRENT / IMPLEMENTED BEHAVIOR | [Local-first policy](CURRENT_POLICY.md#local-first-policy) | [`registry.py`](../graci/registry.py) | [Phase 3E acceptance](../tests/test_phase3e_acceptance.py) | [Phase 3 closure](../phase3e/README.md) |
| COMPUTE-001 | Authoritative 3090 and optional gated 4090 | CURRENT / IMPLEMENTED BEHAVIOR | [Compute policy](CURRENT_POLICY.md#compute-policy) | [`availability.py`](../graci/availability.py), [`distributed.py`](../graci/distributed.py) | [Phase 3E acceptance](../tests/test_phase3e_acceptance.py) | [Phase 3C](../phase3c/README.md) |
| MODEL-001 | Qwen implementer and GLM reviewer/verifier | CURRENT / IMPLEMENTED BEHAVIOR | [Model roles](CURRENT_POLICY.md#model-roles) | [`routing.py`](../graci/routing.py), [`registry.py`](../graci/registry.py) | [Phase 3E acceptance](../tests/test_phase3e_acceptance.py) | [Phase 3 closure](../phase3e/README.md) |
| MEMORY-001 | Memory is bounded context, not authority | CURRENT / IMPLEMENTED BEHAVIOR | [Memory and privacy](CURRENT_POLICY.md#memory-and-privacy) | [`memory_governance.py`](../graci/memory_governance.py), [`memory_execution.py`](../graci/memory_execution.py) | [Memory governance tests](../tests/test_memory_governance.py) | [Phase 4E](../phase4e/README.md) |
| SELFDEV-001 | Governed self-development lifecycle | CURRENT / FUTURE CAPABILITY | [Self-development and self-modification](CURRENT_POLICY.md#self-development-and-self-modification) | No autonomous self-development capability | [Governance checks](../tests/test_governance.py) | — |
| VOICE-001 | Explicit PTT release submission boundary | CURRENT / IMPLEMENTED BEHAVIOR | [Voice and conversational policy](CURRENT_POLICY.md#voice-and-conversational-policy) | [`push_to_talk.py`](../graci/push_to_talk.py), [`browser_ptt.py`](../graci/browser_ptt.py) | [PTT barge-in tests](../tests/test_ptt_barge_in.py) | [Phase 7C](../phase7c/README.md) |
| VOICE-002 | Production speech presentation values | CURRENT / IMPLEMENTED BEHAVIOR | [Voice and conversational policy](CURRENT_POLICY.md#voice-and-conversational-policy) | [`tts.py`](../graci/tts.py), [`pronunciation.py`](../phase6a/pronunciation.py) | [QA-007 tests](../tests/test_qa007_spoken_normalization.py) | [Production voice selection](../PROJECT_STATE.md#production-voice-selection-2026-08-29) |
| VALIDATION-001 | Strict validation and bounded corrective retry | CURRENT / IMPLEMENTED BEHAVIOR | [Failure, retry, validation, and evidence](CURRENT_POLICY.md#failure-retry-validation-and-evidence) | [`validation.py`](../graci/validation.py), [`controller.py`](../graci/controller.py) | [Controller tests](../tests/test_controller.py) | [Structured-response hardening](../PROJECT_STATE.md#governed-model-structured-response-hardening) |
| EVIDENCE-001 | Truthful historical evidence | CURRENT / IMPLEMENTED BEHAVIOR | [Failure, retry, validation, and evidence](CURRENT_POLICY.md#failure-retry-validation-and-evidence) | — | [Governance checks](../tests/test_governance.py) | [Project state](../PROJECT_STATE.md) |

Policy changes follow [CHANGE_PROCESS.md](CHANGE_PROCESS.md). IDs are never silently
reused for a different rule.
