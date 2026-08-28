# GRACI Phase 3D — Distributed Routing / Failover

Phase 3D adds bounded real inference placement without changing the accepted role
policy. Qwen remains implementer/general reasoning and GLM remains reviewer/verifier.
Role selection occurs first; endpoint placement cannot substitute a different model.

## Deterministic routing and freshness

The default is the authoritative 3090. Only a caller's explicit
`prefer_optional=True` request considers the 4090. Each such request performs a new
fixed Phase 3C MO2 query and a new bounded 4090 `/models` query. Both observations
must have valid UTC timestamps no more than 10 seconds old at evaluation, in
addition to every Phase 3C gate passing. Stale, future, or malformed timestamps fail
closed. There is no eligibility cache and no probabilistic or LLM-selected policy.

If eligible, the router makes at most one 4090 `/chat/completions` attempt. If the
gate fails, it makes zero 4090 inference requests and attempts the 3090 once. If the
4090 attempt fails after dispatch, the failure is recorded and the 3090 is attempted
once. A primary failure ends truthfully as FAIL; there is no loop or duplicate retry.
An inference already running is not killed if MO2 starts. The next optional request
performs a new gate check and is blocked once RUNNING is observed. GRACI performs no
remote process control.

## Evidence and shared storage

Every operation atomically writes one uniquely named JSON record containing role,
model, endpoint, node, gate observations and ages, attempts, fallback reason,
server-reported model, contact booleans, final outcome, and `cloud_ai_used: false`.
Accepted live records are stored in `evidence/`.

Shared storage is deliberately not used in Phase 3D. Prompts, responses, health
facts, and JSON evidence are bounded and small, so a shared data path provides no
meaningful transfer advantage. Keeping evidence on the authoritative 3090 avoids
shared mutable state, races, ambiguous authority, and unnecessary availability and
security dependencies. A later phase may use immutable uniquely named artifacts for
large read-only inputs or reviewer artifacts, but their presence can never authorize
4090 inference or bypass Phase 3C.

## Security and limitations

Only fixed OpenAI-compatible llama.cpp `/models` and `/chat/completions` endpoints
and the fixed read-only Phase 3C MO2 endpoint are used. No cloud provider, secret,
remote shell, process enumeration, process termination, general administration,
policy override, or repository mutation service exists. The 3090 remains sufficient
and authoritative. The 10-second rule bounds observation age, but it cannot make the
MO2 check and inference dispatch atomic across two independent services; MO2 may
start immediately after a valid check. In-flight work is allowed to finish or fail,
and subsequent dispatches re-evaluate.

## Verification

Run the warning-strict suite with:

```powershell
python -W error -m unittest discover -s tests -v
```

The warning-strict suite passes 99 tests: all 86 prior regressions and 13 Phase 3D
tests. Live Test A uses `python -m phase3d.run_live_acceptance --expected-node 4090
--expected-mo2-state NOT_RUNNING`. Live Test B uses the same bounded operation with
`--expected-node 3090 --expected-mo2-state RUNNING`.

Test A evidence `1a975f47-55df-4cc5-ad8f-695c6559a78b.json` records fresh
NOT_RUNNING eligibility, one successful 4090 inference, exact Qwen identity, and no
fallback. Test B evidence `5f98916a-700f-4c2f-a7c9-3caa288e5abb.json` records exact
RUNNING/`mo2_running`, zero 4090 inference, and one successful 3090 operation. A
final independent check observed NOT_RUNNING, both models healthy, and eligibility
restored. The Codex offline sandbox blocks private LAN access, so the unchanged
runner executed in the normal 3090 host network context; GRACI policy and network
security were not changed.
