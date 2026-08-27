# GRACI Phase 3A resource and endpoint registry

Phase 3A was accepted on 2026-08-27 from Phase 2 closure commit
`51c14fa510c76da1ffd062d96a7d7fab058a6ce0`. It adds a standard-library-only,
immutable typed registry in `graci/registry.py`; it does not add workload routing.

## Registered topology

- Node `3090` is enabled, required, and primary. Endpoint `3090-llama-cpp` is the
  OpenAI-compatible llama.cpp service at `http://127.0.0.1:8080/v1`.
- Node `4090` is enabled but optional. Endpoint `4090-llama-cpp` records
  `http://192.168.0.101:8080/v1`. Phase 3A policy always makes this node
  ineligible. Its health is unknown and Phase 3A did not contact it.
- `qwen3.8-27b-q4_k_m` has implementer and general-reasoning roles.
- `GLM-4.7-Flash-64x2.6B-Q4_K_M` has reviewer and verifier roles. These roles are
  metadata only; there is no reviewer execution or model switching.

Endpoints have unknown, healthy, or unhealthy health. The bounded health check
validates HTTP 200, UTF-8 JSON, a `data` model list, every model entry, and any
required model IDs. HTTP, timeout, network, JSON, envelope, and model failures are
recorded truthfully. Eligibility is evaluated separately and fails closed for
missing or inconsistent references, disabled resources, unknown or unhealthy
health, unavailable models, unknown roles or policy, and the Phase 3A 4090 block.

## Verification and evidence

The warning-strict suite passed 65 tests: all 58 Phase 1/2 tests plus seven Phase
3A test methods. Compilation, JSON parsing, whitespace checks, security review, and
complete diff review passed.

Live record `f2b15951-f9b7-45c9-9d5b-19cbc3a7e651` contacted only
`http://127.0.0.1:8080/v1/models` with a five-second timeout. It returned HTTP 200
and advertised both registered models. The 3090/Qwen resource evaluated eligible.
The 4090 evaluated ineligible with `policy_blocked_node` and was not live-checked.
The record is in `evidence/` and can be reproduced with
`python -m phase3a.run_live_validation`.

Phase 3A does not route workloads, detect `ModOrganizer.exe`, load balance, fail
over, call cloud AI, switch models during autonomous runs, or execute a reviewer.
The accepted Phase 2 controller still resolves to exactly the localhost 3090 and
Qwen configuration. Phase 3B — Local Model Role Routing is the next authorized
stage.
