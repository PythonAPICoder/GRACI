# ACC-0013: Phase 8E AppLocker incident operational closure

> Classification: durable Product Owner acceptance and live host-validation record
> State: OPERATIONALLY REMEDIATED; FUNCTIONAL WITH HARMLESS RESIDUE
> Recorded: 2026-09-03
> Authority: PO-DEC-040

## Accepted outcome

The Product Owner confirmed that Gate 1, Gate 2, and Gate 3 all passed and accepted
the recovered 3090 host classification as `FUNCTIONAL WITH HARMLESS RESIDUE`. The
Phase 8E Stage 2 AppLocker incident is operationally remediated: normal application
execution works after reboot, no AppLocker rule collection is locally configured or
effective, and no AppLocker warning, error, or deny was recorded after the new boot.

This closure does not restore, approve, or qualify the Stage 2 design. That design
remains unsafe, rejected, superseded, and quarantined. Existing empty-policy and
cache artifacts are residue only and are not authorization for cleanup. The
replacement Phase 8E boundary and any later Phase 8F work remain separate future
work requiring their own explicit Product Owner decisions.

## Three-gate result

| Gate | Result | Accepted boundary |
|---|---|---|
| Gate 1 | **PASS** | The separately authorized first incident-recovery gate completed. |
| Gate 2 | **PASS** | The separately authorized second gate and its pre-reboot checks completed. No further `gpupdate` was authorized or performed during Gate 3. |
| Gate 3 | **PASS** | The new boot and authorized post-reboot read-only validation completed with normal application execution and no effective AppLocker enforcement. |

The Product Owner's current acceptance is authoritative for the Gate 1 and Gate 2
outcomes. The exact final Gate 3 observations are recorded below.

## Final Gate 3 evidence

The audit began at `2026-09-03T13:01:44.2175422-05:00`. Windows 11 Pro build
`26200` reported a new boot time of `2026-09-03T12:53:35.5000000-05:00`
(`2026-09-03T17:53:35.5000000Z`).

### Policy and registry

- Local AppLocker policy: `<AppLockerPolicy Version="1" />`.
- Effective AppLocker policy: `<AppLockerPolicy Version="1" />`.
- No local or effective rule collection exists, so no AppLocker collection is
  enforcing.
- `HKLM\SOFTWARE\Policies\Microsoft\Windows\SrpV2` exists as an empty root with
  zero values and zero child keys.
- No GRACI Stage 2 rule name, path, or rule GUID was present under `SrpV2`.
- `Registry.pol` contains an empty `SrpV2` key record but no `GRACI`,
  `GRACI Phase 8E Stage 2`, staging path, projection path, or Stage 2 rule GUID.

| File | Size | Last write time | SHA-256 |
|---|---:|---|---|
| `C:\Windows\System32\GroupPolicy\Machine\Registry.pol` | 724 bytes | `2026-09-03T12:04:55.4657434-05:00` | `4618675B0DBC589DBC90BBAC205C3F974B0C0249B9B49ABA8142AB0DFECD600C` |
| `C:\Windows\System32\GroupPolicy\gpt.ini` | 166 bytes | `2026-09-03T12:04:55.4657434-05:00` | `6F5EDB450EAC027C35F9C2D53AFD7DEF9509FD93901876CEB170A811FAD6C027` |

`gpt.ini` reported `Version=13`. Both files retained the same size, last-write
time, and hash during the final immutability recheck.

### AppLocker components and residue

`AppIDSvc`, `appid`, and `applockerfltr` were running and configured for demand
start. Their running state does not establish enforcement because both local and
effective policy were empty. The existing AppLocker directory files were:

| File | Size | Creation time | Last write time | SHA-256 |
|---|---:|---|---|---|
| `AppCache.dat` | 16,384 bytes | `2026-09-02T23:42:55.9653369-05:00` | `2026-09-03T12:53:15.6481099-05:00` | `776999D795BF4EEED39278F653473F2AE40C44EB13BEF80CEA755FBDF6A21278` |
| `AppCache.dat.LOG1` | 8,192 bytes | `2026-06-30T21:47:25.9704561-05:00` | `2026-09-02T23:42:55.9653369-05:00` | `44946BCEA489F1228561E4009679BA02E1610DC9D3D731ECB317BDF1855BBCB1` |
| `AppCache.dat.LOG2` | 0 bytes | `2026-06-30T21:47:25.9704561-05:00` | `2026-09-02T23:42:55.9653369-05:00` | `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855` |
| `DLL.AppLocker` | 240 bytes | `2026-09-03T12:28:02.0648884-05:00` | `2026-09-03T12:28:02.0648884-05:00` | `5A6BB4D7F95239FBBE9209DCDDED65AF14AA3DF4BA5B9414C349820CC184880B` |
| `EXE.AppLocker` | 240 bytes | `2026-09-03T12:28:02.0638884-05:00` | `2026-09-03T12:28:02.0638884-05:00` | `5A6BB4D7F95239FBBE9209DCDDED65AF14AA3DF4BA5B9414C349820CC184880B` |

These files, the empty `SrpV2` root, and the running demand-start components are the
harmless residue named by the final classification. Their presence alone does not
prove active enforcement, and no cleanup is authorized by this acceptance.

### Application and event validation

- Classic Windows PowerShell executed a marker command and returned exit code `0`.
- PowerShell 7 executed a marker command and returned exit code `0`.
- Command Prompt executed a marker command and returned exit code `0`.
- Windows Terminal with PowerShell opened a responsive packaged application window.
- Snipping Tool opened a responsive packaged application window.
- Notepad opened a responsive packaged application window without an edit.
- Codex processes were responsive supporting evidence. Per Product Owner direction,
  process-name or window-title matching was not used as a hard stop, and manual
  confirmation of the Codex window remains the authoritative presentation check.

Since the new boot, the four AppLocker logs contained one informational Event 8001
stating that policy applied successfully. They contained no warning, error, deny,
Event 8026, or Event 8027. The application launches did not add a deny event.

Code Integrity remained separate from AppLocker. Its post-boot log contained only
informational Events 3085, 3099, and 3116. Six policies, including
`VerifiedAndReputableDesktop`, activated with status `0x0`. Event 3085 reported
that WHQL driver enforcement would be disabled for this boot session with settings
`0x0`. No Code Integrity warning, error, audit block, or deny was observed.

## Repository validation

- `git diff --check` passed. Git emitted only line-ending conversion notices.
- The warning-strict governance suite passed all 6 tests, including every relative
  Markdown link and anchor check.
- The warning-strict host-system governance suite passed all 6 tests, including the
  Stage 2 quarantine and fail-before-host-access checks.
- The canonical warning-strict suite was also attempted without changing the live
  host. It ran 690 tests and reported 24 errors because the active GRACI resident
  correctly blocked one-shot CLI test entry points. Stopping the resident was not
  authorized by the repository-only closure. The failing cases were runtime
  precondition errors, not documentation, link, or quarantine failures. Four
  synthetic run records created by that attempt were identified against the
  pre-test snapshot and removed; all 392 pre-existing records were preserved.

## Closure boundary

The incident is operationally remediated, not erased. Historical source, evidence,
and acceptance records remain truthful. The rejected AppLocker workflow and its
dependent routine launcher remain quarantined. This acceptance authorizes the
documentation closure, commit, and push only. It does not authorize cleanup of the
harmless residue, another host change, replacement Phase 8E implementation or
deployment, or any continuation of Phase 8F.
