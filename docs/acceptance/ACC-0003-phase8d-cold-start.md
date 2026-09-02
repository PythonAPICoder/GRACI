# ACC-0003 — Phase 8D controlled cold-start validation

> Classification: durable deployment, failure, repair, and repeated-validation record
> State: PRODUCT OWNER ACCEPTED
> Promoted commit: `a0a61b7298d3c85cec054cd11ca827842f2776dd`
> Initial failed run: `bc8f35d52b844889bf74eaa48927721f`
> Repeated passing run: `1df4990ca2ed4dbb87f3f4478027fcf0`
> Recorded: 2026-09-01 (America/Chicago)

## Authorization and promotion

The Product Owner authorized Phase 8D promotion/deployment and a separate controlled
cold-start acceptance procedure. The warning-strict suite passed all 567 tests,
commit `a0a61b7` was pushed to `origin/main`, and the promoted resident was started
through the documented launcher. Before shutdown, the resident reached sustained
`ready` state with its owned process, browser endpoint, primary router, local model
inventory, STT/TTS assets, and lifecycle heartbeat observed.

After the initial procedure exposed a Code Integrity block in the required 3090
router, the Product Owner separately authorized a security-preserving repair:
preserve the active policy, replace the blocked build with a verified official
signed-or-reputable compatible build, deploy it, and repeat the controlled procedure.
This authorization did not weaken security policy or establish Product Owner
acceptance by implication. It is recorded as `PO-DEC-010`.

## Initial controlled cold-start failure

Windows completed a full shutdown and later booted at
`2026-09-02T02:28:25.5000000Z`. A temporary limited current-user collector sampled
the system at 0, 15, 30, 60, 120, and 300 seconds after its logon start. The
temporary scheduled task completed with result `0` and was then removed; ignored raw
evidence remains under `.runtime/cold-start-acceptance/`.

The resident portion remained stable:

- `\GRACI Resident Host` completed with result `0` after the new boot;
- one owned resident instance, PID `13456`, remained alive through five minutes;
- the loopback health and browser endpoints responded throughout the sustained
  checkpoints;
- the browser identity was valid; and
- the resident lifecycle ledger recorded launcher publication and repeated
  heartbeats after the launcher exited.

The complete GRACI runtime did not become ready:

- `\GRACI 3090 llama.cpp Router` completed with result `1`;
- port `127.0.0.1:8080` never became reachable;
- Qwen and GLM were therefore unavailable on the primary 3090 path; and
- Phase 8D correctly reduced overall readiness to `unavailable` while continuing to
  report resident process and browser readiness separately.

The initial automated summary is `FAIL`. This remains truthful historical evidence.

## Established initial failure cause

Windows Code Integrity events `3033` and `3077` at `2026-09-02T02:28:56Z` record
that `E:\llama.cpp\bin\llama-server.exe` attempted to load
`E:\llama.cpp\bin\llama-server-impl.dll`, which did not meet the active enterprise
signing/reputation policy. The enforced policy was `VerifiedAndReputableDesktop`, ID
`{0283ac0f-fff1-49ae-ada1-8a933130cad6}`.

Direct signature inspection reported `NotSigned` for the router executable and its
sampled llama.cpp dependencies. A separate version-only launch reproduced exit
`0xC0E90002` (`STATUS_SYSTEM_INTEGRITY_POLICY_VIOLATION`) and a matching Code
Integrity event. No Code Integrity, Smart App Control, trust, signing, or allowlist
setting was changed.

## Authorized security-preserving repair

Official [llama.cpp release b9637](https://github.com/ggml-org/llama.cpp/releases/tag/b9637),
upstream commit `aedb2a5e9`, was tested outside the production path. Its CUDA 13.3
router archive matched the published SHA-256 digest
`8667e76077b40db57fc680577c6d8b48b8aa3f58e34fc23a70bcc668a69c97e9`.
The separate NVIDIA runtime archive matched
`1462a050eb4c684921ba51dcc4cc488a036674c3e73e9945ee705b854808d03e`;
its CUDA DLL signatures were valid NVIDIA Authenticode signatures.

GitHub's attestation API returned no provenance record for this older release, so
the evidence does not claim an attestation. The b9637 llama.cpp executable and
sampled llama.cpp DLLs are `NotSigned`. The unchanged active
`VerifiedAndReputableDesktop` policy nevertheless permitted the exact candidate,
with no Code Integrity block event. This is live allowability evidence under the
active verification/reputation enforcement, not a code-signing claim. It supported
every GRACI router flag,
listed both approved models, spawned Qwen with the pinned `--n-gpu-layers all`
setting, and served an isolated OpenAI-compatible request.

The replacement was staged and hash-checked before a recoverable directory swap.
The production `llama-server.exe` SHA-256 is
`06444801bb1dc38a848bb5a527728c4ea14ad2aa45ce7e81a29a5fb5d2560eaf`.
The blocked prior directory remains preserved at
`E:\llama.cpp\bin-b10516-ci-blocked-20260902`; the task action and pinned production
path did not change.

## Repeated controlled cold-start pass

Repeat run `1df4990ca2ed4dbb87f3f4478027fcf0` followed a full Windows shutdown and
new boot at `2026-09-02T02:56:45.5000000Z`. The same bounded collector sampled at 0,
15, 30, 60, 120, and 300 seconds. At every sustained 60, 120, and 300 second
checkpoint:

- both exact startup tasks were registered, enabled, `Ready`, had run after the new
  boot, and reported launcher result `0`;
- one owned resident instance, PID `12040`, remained alive with stable instance ID
  `f8f85444d76a4f67a8e2e5d71996fd77`;
- resident health responded with fresh `ready` state;
- the loopback browser responded with the expected GRACI identity;
- the primary router responded with both approved model IDs; and
- the lifecycle ledger retained heartbeats and no terminal event.

The repeated automated summary is `PASS`:

- `boot_advanced`: `true`;
- `tasks_launcher_succeeded_after_boot`: `true`;
- `stable_resident_instance`: `true`; and
- `sustained_process_endpoint_browser_readiness`: `true`.

The temporary collector task completed with result `0` and was removed. Afterward,
live Phase 8D service status and runtime readiness both reported `ready`, and no
llama.cpp Code Integrity block event was present after the repeated boot. Ignored raw
evidence remains under
`.runtime/cold-start-acceptance/1df4990ca2ed4dbb87f3f4478027fcf0/`.

## Product Owner acceptance

Phase 8D is promoted, deployed, and supported by a passing automated controlled
cold-start record. The Product Owner explicitly accepted Phase 8D on 2026-09-01.
`GRACI-ISSUE-001` is closed. This acceptance applies to the documented Phase 8D
capability, deployment, security-preserving 3090 repair, and repeated cold-start
evidence; it does not broaden other authority or acceptance scopes.

The Product Owner has separately identified an optional 4090 llama.cpp upgrade as
required follow-on work and authorized its bounded inspection, implementation,
deployment, rollback verification, and acceptance procedure. That separate objective
must retain its own evidence and cannot inherit Phase 8D acceptance by implication.
