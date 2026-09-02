# ACC-0004 — Optional 4090 llama.cpp upgrade

> Classification: durable inspection, deployment, rollback, and live-validation record
> State: PRODUCT OWNER ACCEPTED
> Recorded: 2026-09-02 (America/Chicago)

## Authorization and boundary

The Product Owner authorized a separate bounded inspection, upgrade, deployment,
rollback verification, and acceptance procedure for the optional RTX 4090
llama.cpp router. The 3090 remained authoritative and sufficient. Every workload
check retained the exact `ModOrganizer.exe` fail-closed gate, and no 4090 work was
performed while MO2 was running.

The Product Owner established Windows PowerShell Remoting from the 3090 to
`VR-Gamer` (`192.168.0.101`) using dedicated administrative identity
`VR-Gamer\GRACI_Remote` as the standard management path. The password was entered
through a native credential prompt, held only in the live PowerShell process, and
was not written to the repository, scripts, prompts, or logs. The temporary
DPAPI-encrypted credential transfer file was deleted after the reusable session was
established.

## Reconstructed prior deployment

Direct remote Windows evidence established:

- root scheduled task `\llama.cpp 4090 Router`, running as `SYSTEM` at startup;
- fixed action `C:\llama.cpp\launch\Router-4090.cmd`;
- production executable `C:\llama.cpp\bin\llama-server.exe`;
- prior b10516 executable SHA-256
  `5a3cbd5613c45ef2d53d3afc6734fd9e67229c0066c2415626ddc7c18901d36c`;
- router flags `--models-max 1`, `--models-autoload`,
  `--sleep-idle-seconds 300`, `--host 0.0.0.0`, `--port 8080`,
  `-ngl 999`, and `-c 98304`; and
- both approved model files under `C:\llama.cpp\models`.

The port-8080 inbound firewall rule permits only remote address
`192.168.0.100`, the controlling 3090. The MO2 endpoint reported exact process
absent / `NOT_RUNNING` before staging, isolated inference, deployment, rollback,
and final validation.

## Candidate provenance and isolated validation

Official llama.cpp release b10675, upstream commit `90c26fcd4`, was selected. The
CUDA 13.3 Windows archive SHA-256 matched the upstream published digest:

`38c23100c05d74ee9893d6875bf0ac4ce69a3fbb9a7fdfc195a71e3f4c2829bd`

GitHub attestation verification succeeded for the archive. After transfer through
the authenticated WinRM session, the remote archive digest matched again. The
candidate `llama-server.exe` SHA-256 was
`5d73e21913c14ba4e94e8e5657d56cfcec4c55d7f91c75be1aff9f731c64bc8b`.
On the 4090 it reported build 10675 and commit `90c26fcd4`.

A temporary loopback-only acceptance task ran the candidate on port 18080 using the
production models and flags. It listed both approved models and completed real Qwen
inference with response `READY` and fingerprint `b10675-90c26fcd4`. The temporary
task was stopped and removed before production deployment.

## Deployment and live rollback proof

The existing production task was stopped, only its exact owned llama.cpp process
was ended, and the candidate directory was promoted to the unchanged pinned
`C:\llama.cpp\bin` path. The original b10516 directory was preserved at:

`C:\llama.cpp\bin-b10516-pre-b10675-20260902`

Rollback was exercised rather than inferred: b10675 was stopped, b10516 was
restored to the production path, and the old router returned both approved model
records. The candidate was subsequently re-promoted, its hash was rechecked, and
the production router again returned both model records. The launch script,
scheduled-task action, model files, firewall rule, and MO2 policy were unchanged.

## Final live validation

At `2026-09-02T00:12:47-05:00`, tests from the controlling 3090 established:

- MO2 schema 1: `NOT_RUNNING`, reason `exact_process_absent`;
- telemetry schema 2 health: `ready`;
- production task: running as `SYSTEM`;
- exactly one production router at the pinned path;
- Qwen returned exactly `READY` with fingerprint `b10675-90c26fcd4`;
- GLM returned exactly `READY` with fingerprint `b10675-90c26fcd4`; and
- the temporary acceptance task no longer existed.

## Controlled restart validation

With separate Product Owner approval, the 4090 was restarted remotely through the
dedicated WinRM path. The procedure observed the host go down and return. Windows
boot time advanced from `2026-08-31T10:50:50-05:00` to
`2026-09-02T00:33:15.5000000-05:00`.

After startup:

- WinRM, MO2 status, telemetry, and the router endpoint returned;
- `\llama.cpp 4090 Router` ran after the new boot and remained running;
- exactly one root router used port 8080, plus the expected loaded-model worker;
- the production executable retained the verified b10675 hash;
- the firewall still allowed only remote address `192.168.0.100`;
- the b10516 rollback directory remained present;
- the temporary acceptance task remained absent;
- MO2 remained exact process absent / `NOT_RUNNING`;
- telemetry returned schema 2 `ready`; and
- Qwen and GLM each returned exactly `READY` with fingerprint
  `b10675-90c26fcd4`.

The automated controlled-restart result is `PASS`. This establishes inspection,
deployment, real two-model inference, executable rollback, and reboot persistence.

## Product Owner acceptance

On 2026-09-02, the Product Owner explicitly accepted the optional 4090 llama.cpp
upgrade and confirmed gaming-impact acceptance as verified. This acceptance covers
the documented b10675 deployment, two-model behavior, rollback, restart persistence,
MO2 protection, and gaming impact. It does not make the 4090 a required dependency
or broaden authority beyond the accepted compute and task boundaries.
