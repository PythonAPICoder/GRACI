# ACC-0006: 4090 telemetry 1.0.1 startup and resource validation

> Classification: durable deployment and live-validation record
> State: PRODUCT OWNER ACCEPTED
> Recorded: 2026-09-02 (America/Chicago)

## Scope and boundary

This record closes the previously missing technical evidence for the deployed
read-only telemetry agent 1.0.1. It covers the fixed scheduled-task contract,
single-instance startup after a controlled 4090 restart, process priority, listener
ownership, telemetry identity and freshness, resource use, HUD reacquisition, and
non-interference observations. The technical result does not grant workload
authority or make the 4090 required. Product Owner acceptance is recorded separately
below.

The procedure used the accepted certificate-authenticated HTTPS WinRM path from the
3090. No password was used or stored. `ModOrganizer.exe` was confirmed absent before
the restart; telemetry was not started manually after the restart.

## Pre-restart evidence

At `2026-09-02T10:33:34-05:00`, direct Windows evidence on `VR-GAMER` established:

- root task `\GRACI 4090 Read-Only Telemetry`, running from an enabled boot trigger;
- limited `SYSTEM` service-account principal;
- fixed action `C:\Jarvis\Python310\python.exe -m telemetry_agent` with working
  directory `C:\ProgramData\GRACI`;
- `MultipleInstances=IgnoreNew`, three restart attempts at one-minute intervals,
  and no execution-time limit;
- exactly one matching process, PID `5588`, created by the boot-time task run;
- effective process priority `BelowNormal`;
- one TCP 8767 listener, owned by PID `5588`, bound only to `192.168.0.101`;
- working set `43,737,088` bytes (41.71 MiB) and private memory `31,559,680`
  bytes (30.10 MiB);
- no CPU-time increase across 15 seconds; and
- no telemetry PID among NVIDIA compute applications.

Three endpoint samples advanced from `2026-09-02T15:33:48Z` through
`15:33:57Z`. They reported schema 2, node `4090`, agent 1.0.1, requested/applied/
observed below-normal priority, RTX 4090 identity, and real GPU, CPU, VRAM, and RAM
observations. The first request included connection setup at 34.370 ms; subsequent
requests were 3.902 and 3.307 ms. MO2 was exact process absent / `NOT_RUNNING`.
The b10675 router exposed both approved models normally.

## Controlled restart and startup result

The approved procedure initiated a normal controlled Windows restart. The new boot
time was `2026-09-02T10:34:38.5000000-05:00`. Certificate WinRM returned without a
password, and no telemetry start command was issued.

At `2026-09-02T10:37:21-05:00`, direct post-boot evidence established:

- the same root task had run at `10:34:56-05:00` from its boot trigger and remained
  in the expected running state;
- exactly one fixed telemetry process existed, PID `4808`, created at
  `10:34:56.257059-05:00`;
- the process remained `BelowNormal` and exclusively owned the listener at
  `192.168.0.101:8767`;
- working set was `43,294,720` bytes (41.29 MiB) and private memory was
  `31,514,624` bytes (30.05 MiB);
- the telemetry PID was absent from NVIDIA compute applications;
- `/health` returned schema 2 `ready`;
- three samples advanced from `2026-09-02T15:37:20Z` through `15:37:26Z`, with
  complete observed GPU/CPU/VRAM/RAM data and 3.156, 3.441, and 3.340 ms request
  latency;
- MO2 remained exact process absent / `NOT_RUNNING`; and
- the b10675 root router returned with both approved models available and unloaded,
  as expected immediately after boot.

The measured memory, CPU, GPU attribution, priority, single-instance behavior, and
steady request latency remain consistent with the qualified baseline. No duplicate
or rapid restart was observed.

## 3090 HUD reacquisition

The 3090 resident was separately found absent with stale state even though its last
launcher result was successful, the known distinction between launcher success and
resident liveness. The existing `\GRACI Resident Host` task was started without
configuration change. Lifecycle evidence recorded the prior unrecorded exit,
starting, launcher publication, and readiness transition to `ready`.

The resident snapshot then automatically reported optional node `4090` telemetry as
`observed`, source `read-only agent v1.0.1`, with a fresh timestamp, RTX 4090
measurements, exact MO2 `NOT_RUNNING`, healthy endpoint state, and independently
computed eligibility. This establishes HUD reacquisition while preserving the
separate fail-closed eligibility decision.

## Result and remaining acceptance boundary

The bounded technical procedure result is **PASS**. Reboot startup, single-instance
behavior, process/listener identity, sustained resource expectations, telemetry
freshness, and HUD reacquisition are now established for agent 1.0.1.

The Product Owner previously verified gaming impact for the accepted 4090
environment while telemetry 1.0.1 was deployed. On 2026-09-02, the Product Owner
explicitly accepted telemetry 1.0.1 on the bounded evidence in this record. That
acceptance covers the documented deployment, controlled startup, single-instance
and resource behavior, endpoint identity/freshness, non-interference observations,
and HUD reacquisition. It grants no workload, routing, or expanded remote-execution
authority.
