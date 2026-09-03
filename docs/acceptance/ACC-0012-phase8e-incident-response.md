# ACC-0012: Phase 8E Stage 2 incident response authority

> Classification: durable Product Owner decision and repository-remediation record
> State: ROOT CAUSE ACCEPTED; OPERATIONAL CLOSURE RECORDED IN ACC-0013
> Recorded: 2026-09-02

## Accepted conclusions

The Product Owner accepted the Phase 8E Stage 2 post-incident root-cause analysis.
Stage 2 caused a serious host-safety incident by enabling machine-wide AppLocker
EXE enforcement without a Packaged App collection. The AppLocker architecture was
disproportionate to the viewer-isolation requirement and is unsafe, rejected, not
approved for deployment, and removed from the current GRACI baseline. Adding a
Packaged App `Allow *` rule is not an acceptable remediation.

This decision supersedes the current approval effect of ACC-0008 and the dependent
routine-launch portion of ACC-0009. Those records and their machine evidence remain
historically truthful for what was tested and accepted at the time.

## Authorized repository work

PO-DEC-039 authorizes incident documentation, current-state reconciliation,
fail-closed quarantine of the AppLocker-dependent workflow, non-deployed replacement
design, governance changes, repository static checks, and design of a future
read-only host audit.

The approved replacement direction uses a dedicated standard viewer identity,
filesystem separation, inert exported content, strict validation, exact manifests
and hashes, generation-immutable projection, constrained viewer configuration, and
an explicit validated launcher. It is approved for design only.

## Explicit boundary

This record does not authorize any Windows host change, host audit, cleanup,
AppLocker or application-control action, service or registry action, ACL change,
account or group change, firewall action, deployment, replacement implementation,
reboot, or Phase 8F work. The current host must be treated as functionally recovered
but unassessed until a separate read-only audit is explicitly approved.

Repository remediation completion and any commit or push remain separate from
acceptance unless the Product Owner explicitly authorizes them.

## Later operational closure

PO-DEC-040 records that the separately authorized Gate 1, Gate 2, and post-reboot
Gate 3 all passed. The Product Owner classified the host as
`FUNCTIONAL WITH HARMLESS RESIDUE`, marked the incident operationally remediated,
and authorized the documentation closure, commit, and push. See
[`ACC-0013`](ACC-0013-phase8e-applocker-operational-closure.md) for the exact final
hashes, timestamps, policy, service, cache, event, and application evidence.

This later closure does not change the conclusions above. Stage 2 remains rejected,
superseded, and quarantined. Replacement Phase 8E and later Phase 8F work remain
separate future work and are not authorized by the closure.
