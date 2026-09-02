# ACC-0005 — One-way 4090 certificate remoting

> Classification: durable security configuration and live-validation record
> State: PRODUCT OWNER ACCEPTED
> Recorded: 2026-09-02 (America/Chicago)

## Decision and boundary

The Product Owner approved one-way certificate-authenticated PowerShell Remoting
from the authoritative 3090 to optional host `VR-Gamer`. The 4090 receives no
administrative trust back into the 3090. The existing password-authenticated path
remains available only as a Product Owner-controlled break-glass route.

This transport supplies technical access, not task authority. Every mutation still
requires current scope, governance, MO2 gating, validation, evidence, and rollback.
The 4090 remains optional and the 3090 remains independently sufficient.

## Deployed configuration

- HTTPS WinRM listener: `VR-Gamer:5986`;
- inbound firewall: `GRACI WinRM HTTPS from 3090`, limited to
  `192.168.0.100`;
- mapped local identity: `VR-Gamer\GRACI_Remote`;
- mapping subject/UPN: `GRACI_Remote@VR-Gamer`;
- client certificate subject: `CN=GRACI-3090-4090-Deployment`;
- client certificate thumbprint:
  `6ea73b462d29f41544e42a9d66b681ddc1c0d4d6`;
- client certificate expiration: `2028-09-02T00:47:45-05:00`;
- private client key: non-exportable in the 3090 current-user certificate store;
- private root-CA key: non-exportable in the 3090 current-user certificate store;
- server certificate: CA-issued, hostname-valid for `VR-Gamer` and
  `VR-Gamer.local`; and
- routine authentication: certificate only, without a password or stored reusable
  password on the 3090.

The one-time password credential was used only to create/correct the server-side
mapping. Its temporary DPAPI-encrypted file was deleted. Temporary PFX, public
certificate, negative-test certificate, file-transfer probe, and superseded client
certificate artifacts were removed after use.

## Verification

The positive certificate session returned:

- host `VR-GAMER`;
- identity `VR-Gamer\GRACI_Remote`;
- administrative elevation `true`; and
- the expected production b10675 router hash.

Certificate-authenticated file transfer succeeded and the probe file was removed.
An unmapped certificate with a valid client-authentication structure was rejected.
The repository-owned helpers
[`new-4090-certificate-session.ps1`](../../ops/new-4090-certificate-session.ps1)
and
[`status-4090-certificate-trust.ps1`](../../ops/status-4090-certificate-trust.ps1)
fail closed on missing, duplicate, invalid, or near-expiry certificate state.

## Controlled restart

The 4090 was restarted using only the certificate-authenticated session. The host
went down and returned with a new boot time of
`2026-09-02T00:49:32.5000000-05:00`. Without a password prompt:

- certificate WinRM reconnected as the mapped elevated identity;
- the HTTPS firewall remained restricted to `192.168.0.100`;
- MO2 remained exact process absent / `NOT_RUNNING`;
- telemetry returned schema 2 `ready`;
- exactly one root router returned with the verified b10675 hash; and
- Qwen and GLM each returned exactly `READY` with fingerprint
  `b10675-90c26fcd4`.

The controlled-restart result is `PASS`. On 2026-09-02, the Product Owner explicitly
accepted the deployed one-way certificate-remoting capability. Acceptance covers
the documented passwordless 3090-to-4090 path, negative-certificate behavior, file
transfer, restart persistence, break-glass password retention, and authority
boundary. It grants no reciprocal 4090 administration of the 3090.
