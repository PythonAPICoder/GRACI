# GRACI operations

> Classification: current topology, procedures, and time-stamped operational evidence
> Authority: descriptive; live state must be rechecked before an operational action
> Verified against: promoted Phase 8D commit `a0a61b7298d3c85cec054cd11ca827842f2776dd`
> Last verified: 2026-09-01

## Stable topology

| Component | Location | Contract |
|---|---|---|
| Authoritative repository | RTX 3090 host, `E:\GRACI` | Canonical source, documentation, local run records, and governed memory |
| Primary model router | `http://127.0.0.1:8080/v1` | Local llama.cpp router; Qwen and GLM allowlist; 3090 remains sufficient |
| Resident visualizer/operator | `http://127.0.0.1:8766/` | Loopback-only observer plus explicit bounded PTT, Restart, and speech claim/lifecycle controls |
| Optional 4090 model router | `http://192.168.0.101:8080/v1` | Optional capacity only; never a baseline dependency |
| Optional 4090 MO2 status | `http://192.168.0.101:8765/graci/v1/mo2` | Exact read-only `ModOrganizer.exe` state used by fail-closed eligibility policy |
| Optional 4090 telemetry | `http://192.168.0.101:8767` | Fixed read-only `/health` and `/telemetry`; presentation only |

Shared storage exists between the machines as optional infrastructure. It is not
authoritative GRACI storage and must not become a dependency without a clear,
separately reviewed benefit. The repository on the 3090 remains authoritative.

## Startup ownership

The 3090 uses separate current-user, limited, at-logon scheduled tasks:

- `\GRACI 3090 llama.cpp Router`
- `\GRACI Resident Host`

Scripts under [`ops/`](../ops/) install, start, stop, remove, and report these named
resources using GRACI-specific state and identity validation. Do not substitute broad
process matching or force-kill unrelated processes.

Direct Windows Task Scheduler enumeration on 2026-09-01 confirmed both exact root
tasks installed, enabled, and `Ready`, with last task result `0`. Their actions,
working directory, current-user interactive logon trigger, and limited principal
matched the repository installers.

For the resident, scheduled-task success proves only that the PowerShell launcher
started a matching resident and then completed successfully. The launcher exits
after startup; Task Scheduler does not thereby prove or supervise continued
resident-process liveness, visualizer endpoint availability, or browser/runtime
readiness. Registration, launcher result, owned-process liveness, and runtime
readiness are separate facts.

The current [`status-graci-login-tasks.ps1`](../ops/status-graci-login-tasks.ps1)
uses exact Task Scheduler root paths and terminating lookup errors. It separately
reports `missing`, `access denied / unknown`, `registered`, and `launcher succeeded`.
It then delegates to component diagnostics that distinguish an owned process from an
actual healthy endpoint. A nonzero exit means one or more required facts were not
established; it must not be rewritten as task absence.

The resident runtime also retains bounded lifecycle evidence at
`.runtime/resident-host/lifecycle.jsonl`. This file is diagnostic evidence only and
contains startup/readiness/heartbeat/terminal facts, not prompts, transcripts,
credentials, authority, or model output.

Useful read-only checks are:

```powershell
.\ops\status-graci-login-tasks.ps1
Invoke-RestMethod http://127.0.0.1:8080/v1/models
Invoke-RestMethod http://192.168.0.101:8765/graci/v1/mo2
Invoke-RestMethod http://192.168.0.101:8767/health
Invoke-RestMethod http://192.168.0.101:8767/telemetry
```

## Operational snapshot — 2026-09-01

- Both 3090 scheduled tasks were installed, enabled, `Ready`, and reported last task
  result `0`. A later direct reconciliation confirmed the exact root paths
  `\GRACI 3090 llama.cpp Router` and `\GRACI Resident Host`; an intervening
  `not installed` report was a restricted-access false negative.
- The 3090 router was healthy; Qwen was loaded and GLM available/unloaded.
- The resident was not active and `127.0.0.1:8766` refused connections despite a
  resident state file. This is recorded with the open cold-start/readiness issue and
  must not be generalized into expected architecture.
- The optional 4090 model router exposed both approved models, unloaded at the
  observation time.
- The MO2 service reported exact process absent / `NOT_RUNNING`.
- Telemetry `/health` and `/telemetry` were live with schema 2, agent 1.0.1, fresh
  observations, RTX 4090 identity, and below-normal effective priority.
- After the Phase 8D diagnostic repair, a direct read-only invocation correctly
  reported both exact root tasks registered and launcher-succeeded, the resident
  stopped with stale state, and the owned router process/endpoint healthy with Qwen
  loaded. Its nonzero exit truthfully reflected resident runtime absence.

These are time-stamped observations, not guarantees of later state.

## Controlled Phase 8D cold-start — 2026-09-01 CDT

The Product Owner authorized promotion/deployment and a separate controlled
cold-start procedure. Commit `a0a61b7` was pushed to `origin/main`. Before shutdown,
the promoted resident reached `ready` with the owned resident, browser endpoint,
router, model inventory, local speech assets, and lifecycle heartbeat observed.

After full shutdown and a new Windows boot, a temporary limited current-user
collector sampled at 0, 15, 30, 60, 120, and 300 seconds. It was removed after
completion; its ignored raw evidence remains under `.runtime/cold-start-acceptance/`.
The resident task succeeded, one owned resident process remained stable, the health
and browser endpoints stayed responsive, and heartbeats continued after the launcher
exited.

The 3090 router task returned `1` and port `8080` stayed closed. Code Integrity
events `3033` and `3077` identified unsigned
`E:\llama.cpp\bin\llama-server-impl.dll` as violating the active
`VerifiedAndReputableDesktop` policy. A read-only signature audit reported the
sampled llama.cpp executable and dependencies `NotSigned`; a version-only launch
reproduced `STATUS_SYSTEM_INTEGRITY_POLICY_VIOLATION`. Phase 8D therefore reported
the runtime `unavailable` while truthfully preserving the resident/browser-ready
facts.

Code Integrity, Smart App Control, and related trust enforcement were not disabled as
an operational workaround. At that point repair required explicit Product Owner
security direction and a reviewed trusted/signed/reputable router artifact or
signing/trust path. The authorized outcome is recorded below. See
[`ACC-0003`](acceptance/ACC-0003-phase8d-cold-start.md) and
[`GRACI-ISSUE-001`](KNOWN_ISSUES.md#graci-issue-001--cold-startruntime-readiness-failure).

## 3090 router repair and repeated cold start — 2026-09-01 CDT

The Product Owner authorized a security-preserving router repair and repeated
controlled procedure. Official llama.cpp b9637 CUDA 13.3 archives were downloaded
from the [upstream release](https://github.com/ggml-org/llama.cpp/releases/tag/b9637)
and matched these published SHA-256 digests:

- router archive:
  `8667e76077b40db57fc680577c6d8b48b8aa3f58e34fc23a70bcc668a69c97e9`;
- NVIDIA runtime archive:
  `1462a050eb4c684921ba51dcc4cc488a036674c3e73e9945ee705b854808d03e`.

GitHub's attestation API had no provenance record for this older artifact, so no
attestation claim is made. The executable is not Authenticode-signed, but the active
`VerifiedAndReputableDesktop` policy permitted the exact candidate. Because the
llama.cpp files are unsigned, this is live allowability evidence under the active
verification/reputation enforcement, not a code-signing claim. It launched without
Code Integrity events, supported every pinned GRACI flag, listed both approved
models, spawned Qwen with the pinned `--n-gpu-layers all` setting, and served an
isolated OpenAI-compatible request. The production server hash is
`06444801bb1dc38a848bb5a527728c4ea14ad2aa45ce7e81a29a5fb5d2560eaf`.

The b9637 files were installed at the existing pinned `E:\llama.cpp\bin` path. The
blocked b10516 directory was moved intact to
`E:\llama.cpp\bin-b10516-ci-blocked-20260902`; ignored before/after manifests remain
under `.runtime/router-repair/deployment-manifests/`. No task action or security
policy changed.

Repeat run `1df4990ca2ed4dbb87f3f4478027fcf0` booted at
`2026-09-02T02:56:45.5000000Z` and sampled at 0, 15, 30, 60, 120, and 300 seconds.
Both startup tasks returned `0` after that boot. One resident instance, browser and
health endpoints, both primary-router model IDs, and lifecycle heartbeats remained
valid through the final sample. Its summary is `PASS`; the temporary collector task
returned `0` and was removed. No llama.cpp Code Integrity block event was present
after the repeated boot. Raw ignored evidence remains under
`.runtime/cold-start-acceptance/1df4990ca2ed4dbb87f3f4478027fcf0/`.

The Product Owner accepted Phase 8D after reviewing this evidence. The separately
authorized optional 4090 llama.cpp upgrade must preserve 3090 sufficiency,
optional-node gating, MO2 gaming priority, and its own deployment/rollback and
acceptance boundaries.

## Telemetry deployment versus acceptance

Telemetry agent 1.0.1 deployment is confirmed. Full reboot/startup, sustained
resource, duplicate-process, gaming-impact, and Product Owner acceptance remain
unestablished. The reviewed deployment/update/rollback and separate reboot procedure
remain in [`telemetry_agent/README.md`](../telemetry_agent/README.md).
