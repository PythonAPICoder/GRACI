# ACC-0003 — Phase 8D controlled cold-start validation

> Classification: durable deployment and failed-validation record
> State: DEPLOYED / COLD-START VALIDATION FAILED / PRODUCT OWNER ACCEPTANCE NOT ESTABLISHED
> Promoted commit: `a0a61b7298d3c85cec054cd11ca827842f2776dd`
> Evidence run: `bc8f35d52b844889bf74eaa48927721f`
> Recorded: 2026-09-01 (America/Chicago)

## Authorization and promotion

The Product Owner authorized Phase 8D promotion/deployment and a separate controlled
cold-start acceptance procedure. The warning-strict suite passed all 567 tests,
commit `a0a61b7` was pushed to `origin/main`, and the promoted resident was started
through the documented launcher. Before shutdown, the resident reached sustained
`ready` state with its owned process, browser endpoint, primary router, local model
inventory, STT/TTS assets, and lifecycle heartbeat observed.

## Controlled cold-start result

Windows completed a full shutdown and later booted at
`2026-09-02T02:28:25.5000000Z`. A temporary limited current-user collector sampled
the system at 0, 15, 30, 60, 120, and 300 seconds after its logon start. The
temporary scheduled task completed with result `0` and was then removed; ignored
raw evidence remains under `.runtime/cold-start-acceptance/`.

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

The automated summary is `FAIL`. This is validation evidence, not Product Owner
acceptance.

## Established failure cause

Windows Code Integrity events `3033` and `3077` at `2026-09-02T02:28:56Z` record
that `E:\llama.cpp\bin\llama-server.exe` attempted to load
`E:\llama.cpp\bin\llama-server-impl.dll`, which did not meet the active enterprise
signing/reputation policy. The enforced policy was
`VerifiedAndReputableDesktop`, ID `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`.

Direct signature inspection reported `NotSigned` for the router executable and its
sampled llama.cpp dependencies. A separate version-only launch reproduced exit
`0xC0E90002` (`STATUS_SYSTEM_INTEGRITY_POLICY_VIOLATION`) and a matching Code
Integrity event. No Code Integrity, Smart App Control, trust, signing, or allowlist
setting was changed.

## Acceptance boundary and next decision

Phase 8D is promoted and deployed, but it is not cold-start accepted or Product
Owner accepted. `GRACI-ISSUE-001` remains open. Repair requires a separate security
decision: prefer a trusted/signed/reputable 3090 llama.cpp artifact or an explicitly
reviewed signing/trust path; do not weaken the active Code Integrity policy by
implication. After an authorized repair, repeat the controlled cold-start procedure
and obtain explicit Product Owner disposition.
