# Phase 8F Stage 1: synthetic trusted secret broker

> Classification: accepted synthetic design and implementation record
> Authority: PO-DEC-037 and PO-DEC-038; canonical policy remains under `governance/`
> Designed against: `main` commit `a80a2adde10716ee6cfd79dd97c046014f61d15d`
> Prepared: 2026-09-02
> Status: PRODUCT OWNER ACCEPTED; SYNTHETIC ONLY; NOT DEPLOYED

## Outcome and authority boundary

Phase 8F Stage 1 provides a separate synthetic foundation for brokered secret use
and default-deny capability grants. It demonstrates how an authenticated caller can
request one exact operation without receiving the secret value. The broker releases
plaintext only inside the selected synthetic adapter call and returns a bounded
result containing identifiers and status codes.

The implementation consists of:

- [`phase8f/crypto.py`](../phase8f/crypto.py), a Windows CNG AES-256-GCM wrapper;
- [`phase8f/protocol.py`](../phase8f/protocol.py), a canonical HMAC-SHA256 request
  envelope;
- [`phase8f/broker.py`](../phase8f/broker.py), the synthetic store, grant lifecycle,
  dispatcher, audit, transaction, and rollback foundation; and
- [`phase8f/synthetic_adapter.py`](../phase8f/synthetic_adapter.py), one fake notice
  destination with no transport or external side effect.

This work does not expand G.R.A.C.I.'s authority. A proposal, grant record, secret
reference, protocol message, audit event, adapter, test result, model response, or
document cannot create Product Owner approval. The code and tests establish only
the named synthetic behavior.

PO-DEC-037 did not authorize real credentials or real personal data; Windows
account, certificate, TPM, ACL, service, firewall, network, resident, controller,
Obsidian, 3090, or 4090 changes; external or cloud access; dependency installation;
live IPC or service registration; deployment; automatic refresh; ordinary runtime
integration; commit; push; or a later Phase 8F stage. PO-DEC-038 subsequently
accepted the reviewed synthetic foundation and authorized only its commit and push.
None of the other excluded actions occurred in Stage 1 or became authorized.

## Threat model

Stage 1 treats every request, payload, stored file, prior generation, adapter
outcome, exception, and time observation as potentially malformed or stale. It also
assumes that prompt content, memory, Obsidian notes, and model output are untrusted
and cannot authorize a grant or obtain a secret.

| Threat | Implemented Stage 1 response | Limit |
|---|---|---|
| Raw secret disclosure through an API | There is no public raw-secret retrieval or export operation. Requests contain only an opaque secret reference. | Python, native libraries, and the operating system may retain copies outside buffers that Stage 1 can clear. |
| Forged or altered requests | The exact canonical request is authenticated with HMAC-SHA256 under an injected synthetic key. | The in-process synthetic key is not a qualified production caller identity. |
| Replay, stale state, and scope substitution | Request IDs, nonce hashes, expected generation, grant version, caller, key, scope, resource, secret version, adapter, operation, and destination are checked exactly. | Stage 1 has no distributed replay service or live IPC boundary. |
| Prompt injection or false authority | Protocol payloads cannot carry authority or secret fields. Exact Product Owner approval records are created outside model and content paths. | No ordinary typed-turn or PTT approval authenticator is connected. |
| Secret or adapter output leakage | Secret wrappers have redacted representations, mutable buffers are cleared best-effort, and adapter exceptions and outcomes are reduced to fixed typed results. | A future real connector requires its own data minimization and side-effect review. |
| Stored-state tampering, remote storage, or partial writes | Strict schemas, fixed-local-volume enforcement, exact generation trees, hashes, authenticated markers, authenticated encryption, staged verification, and an authenticated current pointer fail closed. | Storage deletion and denial of service remain possible. No backup system exists. |
| Clock rollback | The broker rejects a trusted time observation earlier than the last accepted observation. | Production time authority and recovery after a clock fault are undecided. |
| Recovery that revives authority | Secret rollback creates a new generation and places active grants on recovery hold with a new grant version. | Release from recovery hold is intentionally unimplemented. |

Stage 1 does not claim protection against a compromised Windows administrator,
kernel, broker process, debugger, crash dump, page file, hardware attack, or physical
access. It does not establish secure erasure. The Product Owner has separately
accepted unencrypted local storage as a physical-security risk and prohibited
BitLocker changes. This implementation neither changes nor broadens that decision.

## Trust boundaries and identities

The Product Owner remains the only human authority. Stage 1 can represent an exact
approval from a typed turn or PTT release, but it does not authenticate the speaker
or connect to either live boundary. Tests construct those approval records directly.

The synthetic fixture maintainer is the only accepted provisioner identity. It may
place a runtime-generated fake value into the encrypted test store. Provisioning
requires the exact current generation plus an allowlisted adapter, operation, and
destination. It returns only a new opaque `sec_` reference.

The protocol authenticator is configured for one exact synthetic caller and key ID.
The caller transfers a mutable HMAC key buffer to the authenticator, which clears the
caller buffer and clears its owned buffer best-effort when closed. An unknown caller,
unknown key ID, and invalid MAC produce the same fixed failure.

The broker accepts only explicitly registered synthetic adapters. Stage 1 registers
one fake notice operation and one exact synthetic destination and resource. The
adapter has no socket, network, filesystem, subprocess, model, memory, resident, or
ordinary-runtime dependency.

Models, ordinary G.R.A.C.I. composition, governed memory, Obsidian, run records,
command lines, logs, exceptions, and test evidence remain outside the secret path.
No Stage 1 module is imported by the ordinary operator, controller, resident, or
viewer.

## Authenticated local protocol contract

[`ProtocolRequest`](../phase8f/protocol.py) contains one exact field set:

- schema version;
- canonical UUID request, grant, and expected-generation IDs;
- a positive grant version;
- fixed caller, key, adapter, operation, destination, scope, resource, and opaque
  secret-reference identifiers;
- a timezone-aware issue time normalized to canonical UTC;
- a fixed-size random URL-safe nonce; and
- a small mapping whose keys and values are strings and whose key names cannot
  describe raw secrets, credentials, passwords, tokens, cookies, or key material.

The envelope contains only the request object and its HMAC-SHA256 tag. Encoding uses
sorted keys, fixed separators, ASCII JSON escaping, and no non-finite JSON values.
Decoding rejects non-canonical encoding, duplicate keys at any object depth, unknown
or missing fields, malformed identifiers, malformed timestamps or nonces, nested or
non-string payload values, and payload or envelope size violations.

The HMAC covers the complete request, including the expected generation, grant
version, scope, resource, operation, destination, opaque reference, issue time,
nonce, and payload. The request digest covers the same canonical body and is used for
idempotency and conflict detection. Freshness validation is explicit and currently
uses a two-minute maximum age and ten-second future skew in the broker.

The protocol is an in-process codec only. It creates no listener, pipe, socket,
service, file, or command-line interface. Calling it a local protocol describes the
message contract that a future separately qualified Windows transport could carry.

## Secret protection and non-disclosure

The synthetic encrypted store uses the Windows CNG implementation of AES-256-GCM
through Python standard-library `ctypes`. The cipher requires a 32-byte mutable key,
a 12-byte unique nonce, a 16-byte authentication tag, and purpose-specific associated
data. It uses the Windows preferred random generator and rejects a nonce already
used by the current cipher instance. There is no plaintext or non-Windows fallback.

Cipher and HMAC keys are supplied at runtime for synthetic tests. Caller-visible key
buffers are cleared after transfer. Plaintext inputs, native plaintext buffers,
decrypted mutable buffers, and adapter-owned secret buffers are cleared best-effort
at their defined boundaries. Cipher and secret wrapper representations are redacted.
Stage 1 does not persist either key and therefore does not solve restart, backup, or
key-recovery custody.

The encrypted vault gives every stored secret a fixed 4,096-byte slot and supports
at most 12 synthetic secrets. This bounds storage and reduces per-secret length
leakage inside the vault format. Public metadata still reveals the number of secret
records and their opaque references, versions, allowed adapter, operation, and
destination.

No protocol request, grant, audit event, state record, operation result, receipt,
exception, or representation contains secret plaintext. Adapter execution receives
an owned mutable wrapper only after all request and grant checks pass. Its result is
sanitized to an allowlisted code and, on success, the exact request and notice UUIDs.
Malformed results, mismatched receipts, and adapter exceptions become fixed failures
without input echo.

## Capability-grant lifecycle

A proposal is inert. It binds the caller and key identity, one canonical named
synthetic task or project scope, resource UUID, secret reference and version,
adapter, operation, destination, validity interval, use limit, and optional review
time. Its canonical digest covers
the complete proposal. Reusing an operation ID with different content is an
idempotency conflict.

Activation requires an exact approval record with Product Owner authority, the
proposal ID and digest, a canonical source-turn UUID, and either the `typed_turn` or
`ptt_release` channel. A mismatch, stale generation, expired proposal, changed
secret binding, or reused operation fails closed. This structure records claimed
approval provenance for synthetic testing. It does not authenticate a live Product
Owner action.

| Grant type | Implemented bound |
|---|---|
| One-time | Exactly one reserved use, no review time, and a maximum lifetime of one day. |
| Standing | Between 2 and 100 reserved uses, a required review time before expiry, and a maximum lifetime of 30 days. |

Every operation request must match the active grant exactly and present the current
grant version and current store generation. The broker checks not-before, expiry,
review, status, and remaining uses. A request issued before the grant's not-before
time cannot age into authority and must be replaced by a fresh authenticated
request. The broker reserves and consumes one use in a committed generation before
releasing a secret to the adapter. A failed or uncertain adapter operation does not
restore that use. One-time authority is therefore exhausted before any possible
side effect.

An identical request ID and digest returns the recorded result without another
adapter call. Reusing the request ID with different content is a replay conflict.
Reusing a nonce is denied. A request reserved before an interrupted completion is
reported as outcome uncertain and is never retried automatically. An exact Product
Owner resolution record can close it as unknown without retrying it.

The same Windows store lock remains held from reservation validation and commit
through reservation reload, the synthetic adapter call, and completion persistence.
This prevents revocation, rollback, or uncertain-outcome resolution from overtaking
a live dispatch. A process interruption releases the operating-system lock and
leaves the persistent reservation available for explicit later resolution.

Revocation requires an exact Product Owner record naming the grant and current grant
version. It changes status to revoked and advances the version. Expired,
review-due, exhausted, revoked, and recovery-held grants deny use. Stage 1 provides
no pause, renewal, scope expansion, grant editing, automatic approval, or standing
authority beyond the exact stored grant.

Grant approval, revocation, uncertain-outcome closure, and rollback preserve the
complete synthetic approval record in the authenticated audit chain. Idempotent
replay compares the original expected generation, exact object and version or hash,
source turn, channel, authority, and decision. Changing any of those fields is a
conflict rather than an accepted replay.

## Store, audit, and transaction behavior

The store root must be an absolute drive-letter path on a fixed local Windows
volume. Initialization requires that the target not exist; opening an existing
store uses the ordinary constructor. Windows drive-type inspection rejects mapped
network, removable, optical, RAM-disk, unknown, and invalid volumes. UNC, device,
alternate-data-stream, symbolic-link, and reparse-point paths are also rejected.
Reads require bounded regular files and detect size or timestamp changes during the
read. An in-process lock and a Windows file lock serialize synthetic mutations and
fence each live dispatch through its completion record.

Stage 1 limits the store to 12 secrets, 64 proposals, 64 grants, 256 operation
requests, and 1,024 audit events under an eight-mebibyte state-file ceiling. These
conservative joint bounds keep the logical maxima below the enforced serialized
size budget. Metadata-only snapshot, audit, and grant queries authenticate the
manifest, state, and encrypted-vault hash without expanding secret plaintext.

Initialization writes a `SYNTHETIC_ONLY` boundary marker. Its fixed fields deny real
credentials, real personal data, ordinary runtime integration, live IPC, network
access, deployment, automatic refresh, and key persistence. A missing, altered, or
expanded marker prevents the broker from opening.

Initialization builds and verifies a complete store under a random sibling staging
name, then publishes it with one same-volume Windows write-through move. Each later
mutation creates a complete immutable generation. Plain metadata state and the
encrypted vault are staged with exclusive writes and flushed to disk. The generation
includes an exact manifest, file hashes and sizes, an AES-GCM-authenticated manifest
marker, and an audit chain. The staged generation is read and verified, promoted
with a same-volume Windows write-through move, read and verified again, and only
then selected through an authenticated write-through `current.json` replacement.
The selected pointer and generation are authenticated again before success returns.

Audit records contain a sequence number, event type, UTC time, operation and object
identifiers when applicable, result code, prior event hash, and current event hash.
They do not contain a secret value, request payload, prompt, model content, command
line, adapter exception, or raw destination output. The audit hash chain is verified
as part of the authenticated generation. It is not a separate external timestamp or
append-only security service.

A failure before current-pointer selection leaves the prior current generation
authoritative. An incomplete staging generation or a completely promoted but
unselected generation may remain after a failure and is not current. If pointer
replacement succeeds but immediate post-selection verification fails, the broker
reports outcome uncertain. A use reservation in that state never dispatches. A
completion in that state is never
automatically retried. Other mutations return any already-generated nonsecret
object identifiers needed for exact inspection. A failed initialization can leave
an unselected sibling staging root, while its requested target remains absent and
retryable with new synthetic keys. Stage 1 does not automatically delete historical
generations or every possible orphan because retention and secure deletion policy
remain undecided.

Stage 1 still uses path checks followed by name-based file opens. A privileged local
race can replace a checked file before it is opened. Handle-pinned file identity and
no-reparse enforcement belong with the future Windows account and ACL boundary and
remain unresolved production work.

## Recovery and rollback

Technical secret rollback requires exact Product Owner approval naming the current
generation, target generation, target manifest hash, source turn, channel, and a
unique operation ID. Rollback is denied while an operation remains reserved. It
loads and verifies the target, restores only its secret inventory into the current
state, keeps current grants, requests, and audit history, places every active grant
on recovery hold, advances those grant versions, appends an audit event, and creates
a new generation. It never moves the current pointer backward or rewrites history.

Rollback cannot silently revive permission. A restored secret is unusable through
an active pre-rollback grant because that grant is held and version-changed. No
automatic recovery-hold release exists. A future design must decide whether release
requires reapproval, replacement grants, or another narrower recovery procedure.

Stage 1 does not implement persistent key custody, key rotation, backup, restore to
a new machine, secure deletion, generation retention, disaster recovery, production
clock repair, or recovery from loss of either synthetic key. Those topics require a
separate Product Owner decision before real data or deployment.

## Deterministic verification

The focused tests are:

- [`test_phase8f_crypto.py`](../tests/test_phase8f_crypto.py), covering CNG
  encryption and authentication, tampering, nonce uniqueness and reuse, fixed
  failures, buffer clearing, backend closure, and import isolation;
- [`test_phase8f_protocol.py`](../tests/test_phase8f_protocol.py), covering canonical
  round trips, exact fields, duplicate keys, MAC and identity failures, freshness,
  identifiers, payload bounds, grant-version and scope binding, request digests,
  non-disclosure, and closure;
- [`test_phase8f_synthetic_adapter.py`](../tests/test_phase8f_synthetic_adapter.py),
  covering the one exact fake operation, destination and scope isolation, payload
  denial, redacted representations, buffer clearing, malicious outcomes and
  exceptions, sanitized receipts, and import isolation; and
- [`test_phase8f_broker.py`](../tests/test_phase8f_broker.py), covering the integrated
  synthetic lifecycle, exact approval, one-time and standing grants, expiry,
  revocation, canonical named scopes, stale state, replay, prompt-injection
  isolation, transaction failure, uncertain outcomes, dispatch-versus-resolution
  fencing, rollback, fixed-local-volume enforcement, tampering, and ordinary-runtime
  import isolation. They also verify that public metadata queries do not expand the
  secret vault plaintext.

Run the focused warning-strict verification with:

```powershell
python -W error -m unittest tests.test_phase8f_crypto tests.test_phase8f_protocol tests.test_phase8f_synthetic_adapter tests.test_phase8f_broker -v
```

At the 2026-09-02 review boundary, that focused command passed all 52 tests. The
final pre-commit canonical `python -W error -m unittest discover -s tests -v`
command passed all 684 repository tests. Governance link checks, compilation, and
`git diff --check` also passed. These results are verification evidence and do not
establish deployment or production fitness. An independent architecture and
adversarial re-review found no remaining P0/P1 or material P2 issue at this
boundary. The Product Owner separately accepted the reviewed Stage 1 foundation
under PO-DEC-038.

Passing tests establish only deterministic behavior for runtime-generated synthetic
fixtures on the tested Windows host. They do not prove resistance to process or
administrator compromise, real credential safety, live caller authentication,
transport security, deployment, or operational recovery.

## Future Windows qualification

Production work must begin with a new exact Product Owner decision. It must select
and test the Windows broker identity, caller identity and authentication mechanism,
key protector and persistence mechanism, local IPC transport, ACLs, process and
service isolation, installation root, backup and restore behavior, key rotation,
recovery-hold policy, audit retention, secure deletion expectations, and rollback
procedure. Candidate Windows facilities may be investigated only within the scope of
that later authorization. Stage 1 selects none of them.

Each real connector also needs a separate allowlisted operation contract, destination
identity, resource scope, least-privileged credential, payload schema, result schema,
side-effect model, failure semantics, and adversarial test. Read, search, draft,
send, edit, delete, share, purchase, and administrative operations must remain
separate capabilities. The Stage 1 fake notice adapter does not qualify any real
service or authorize network access.

A future ordinary-runtime adapter must authenticate a direct Product Owner decision
at the trusted typed-turn or explicit PTT-release boundary. Models, prompts, memory,
retrieved text, Obsidian notes, connector content, and tool output must remain unable
to construct an approval or grant. The broker must remain outside model context, and
ordinary G.R.A.C.I. should receive only the minimum sanitized operation result.

## Product Owner acceptance boundary

The Product Owner accepted Stage 1 for repository preservation under PO-DEC-038 and
authorized committing and pushing the reviewed changes to `main`. Automated
verification did not create that authority, and acceptance does not establish
deployment or production fitness.

Windows qualification, real secrets, live IPC, deployment, runtime integration, a
real connector, and Stage 2 remain unauthorized. Any future Windows qualification
or production implementation requires its own explicit scope after unresolved
identity, key custody, transport, recovery, retention, and autonomy decisions
are reviewed. See [`ACC-0011`](acceptance/ACC-0011-phase8f-stage1.md).
